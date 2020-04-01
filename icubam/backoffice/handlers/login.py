import tornado.escape

from icubam.backoffice.handlers.base import BaseHandler


class LoginHandler(BaseHandler):

  ROUTE = "/login"

  ERROR = 'Authentication failed'

  def get(self, error=""):
    # User already logged in, just redirect to the home.
    if self.get_current_user():
      return self.redirect(self.get_argument("next", "/"))
    return self.render("login.html", error=error)

  def post(self):
    email = self.get_body_argument("email", "")
    password = self.get_body_argument("password", "")
    userid = self.store.auth_user(email, password)
    if userid is not None:
      self.set_secure_cookie(self.COOKIE, tornado.escape.json_encode(userid))
      return self.redirect(self.get_argument("next", "/"))

    locale = self.get_user_locale()
    err = self.ERROR if locale is None else locale.translate(self.ERROR)
    return self.get(error=err)
