import functools
import io
import os
from datetime import datetime

import tornado.web
from absl import logging  # noqa: F401

from icubam.db import store, synchronizer
from icubam.analytics import operational_dashboard
from icubam.analytics.preprocessing import preprocess_bedcounts
from icubam.www.handlers import base, home


def _get_headers(collection, asked_file_type):
  if asked_file_type not in {'csv'}:
    return dict()

  datestr = datetime.now().strftime('%Y-%m-%d_%Hh%M')
  filename = f'{collection}_{datestr}.csv'
  headers = {
    'Content-Type': "text/csv",
    'Content-Disposition': f'attachment; filename={filename}'
  }
  return headers


class DBHandler(base.APIKeyProtectedHandler):

  ROUTE = '/db/(.*)'
  API_COOKIE = 'api'
  ACCESS = [
    store.AccessTypes.STATS, store.AccessTypes.ALL, store.AccessTypes.UPLOAD
  ]
  GET_ACCESS = [store.AccessTypes.ALL, store.AccessTypes.STATS]
  POST_ACCESS = [store.AccessTypes.UPLOAD, store.AccessTypes.STATS]

  def initialize(self, upload_path, config, db_factory):
    super().initialize(config, db_factory)
    self.upload_path = upload_path

    keys = ['icus', 'regions']
    self.get_fns = {k: getattr(self.db, f'get_{k}', None) for k in keys}
    self.get_fns['all_bedcounts'] = self.db.get_bed_counts
    self.get_fns['bedcounts'] = functools.partial(
      self.db.get_visible_bed_counts_for_user, user_id=None, force=True
    )

  @base.authenticated(code=503)
  def get(self, collection):
    if self.current_user.access_type not in self.GET_ACCESS:
      logging.info(
        f"API called with incorrect access_type: {self.current_user.access_type}."
      )
      self.set_status(403)
      return

    file_format = self.get_query_argument('format', default=None)
    max_ts = self.get_query_argument('max_ts', default=None)
    # should_preprocess: whether preprocessing should be applied to the data
    # the raw data of ICUBAM contains inputs errors and this preprocessing will
    # attempt to fix them
    # it should be used cautiously because it alters the data in ways that are
    # useful for analysis purposes but not necessarily reflect the exact/real
    # bed count values
    # whenever a query argument named 'preprocess' is present, we enable this
    # preprocessing (it can be 'preprocess=<anything>' or simply 'preprocess')
    should_preprocess = (
      self.get_query_argument('preprocess', default=None) is not None
    )
    data = None

    get_fn = self.get_fns.get(collection, None)
    if get_fn is None:
      logging.debug("API called with incorrect endpoint: {collection}.")
      self.redirect(home.HomeHandler.ROUTE)
      return

    if collection in ['bedcounts', 'all_bedcounts']:
      if isinstance(max_ts, str) and max_ts.isnumeric():
        max_ts = datetime.fromtimestamp(int(max_ts))
      get_fn = functools.partial(get_fn, max_date=max_ts)
      data = store.to_pandas(get_fn(), max_depth=2)
      data = data.drop(columns=['icu_bed_counts', 'icu_users', 'icu_managers'])
      if collection == 'all_bedcounts' and should_preprocess:
        data = preprocess_bedcounts(data)
    else:
      data = store.to_pandas(get_fn(), max_depth=0)

    for k, v in _get_headers(collection, file_format).items():
      self.set_header(k, v)

    if file_format == 'csv':
      stream = io.StringIO()
      data.to_csv(stream, index=False)
      self.write(stream.getvalue())
    else:
      self.write(data.to_html())

  @tornado.web.authenticated
  def post(self, collection):

    if self.current_user.access_type not in self.POST_ACCESS:
      logging.info(
        f"API called with incorrect access_type: {self.current_user.access_type}."
      )
      self.set_status(403)
      return

    # Send to the correct endpoint:
    if collection == 'bedcounts':
      csvp = synchronizer.CSVPreprocessor(self.db)

      # Get the file object and format request:
      file = self.request.files["file"][0]
      file_format = self.get_query_argument('format', default=None)
      file_name = None
      # Pre-process with the correct method:
      if file_format == 'ror_idf':
        input_buf = io.StringIO(file["body"].decode('utf-8'))
        try:
          csvp.sync_bedcounts_ror_idf(input_buf)
        except Exception as e:
          logging.error(f"Couldn't sync: {e}")
        file_name = 'ror_idf'
      else:
        logging.debug("API called with incorrect file_format: {file_format}.")
        self.set_status(400)
        return

      # Save the file locally just in case:
      time_str = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
      file_path = os.path.join(self.upload_path, f"{time_str}-{file_name}")
      try:
        with open(file_path, "wb") as f:
          f.write(file["body"])
        logging.info(f"Received {file_path} from {self.request.remote_ip}.")
      except IOError as e:
        logging.error(f"Failed to write file due to IOError: {e}")

    # Or 404 if bad endpoint:
    else:
      logging.error(f"DB POST accessed with incorrect endpoint: {collection}.")
      self.set_status(404)
      return


class OperationalDashboardHandler(base.APIKeyProtectedHandler):

  ROUTE = '/dashboard'
  # Problably better not to be equal to admin.
  BACKOFFICE_PREFIX = 'static_bo/'
  API_COOKIE = 'api'
  ACCESS = [store.AccessTypes.STATS, store.AccessTypes.ALL]

  @base.authenticated(code=503)
  def get(self):
    """Serves a page with a table gathering current bedcount data with some extra information."""
    arg_region = self.get_query_argument('region', default=None)
    locale = self.get_user_locale()
    kwargs = operational_dashboard.make(
      self.current_user.external_client_id,
      self.db,
      arg_region,
      locale,
      self.config.backoffice.extra_plots_dir,
      external=True
    )

    parent_path = '/'.join(os.path.split(self.PATH)[:-1])
    template_folder = os.path.join('/', parent_path, 'backoffice/templates/')
    return self.render(
      os.path.join(template_folder, 'operational-dashboard.html'),
      backoffice_root=self.BACKOFFICE_PREFIX,
      api_key=self.get_query_argument('API_KEY', None),
      **kwargs
    )
