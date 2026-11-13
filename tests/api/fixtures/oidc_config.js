var getOidcConfig = function () {
  var config = {
    authority: 'https://accounts.magister.net',
    client_id: 'M6-' + window.location.hostname,
    redirect_uri: 'https://' + window.location.hostname + '/oidc/redirect_callback.html',
    response_type: 'id_token token',
    scope: 'openid profile opp.read opp.manage attendance.overview attendance.administration calendar.user calendar.ical.user calendar.to-do.user grades.read grades.manage oso.administration registration.admin lockers.administration exams.administration enrollment.admin privacyportal.administration learningmaterials.user',
    post_logout_redirect_uri: 'https://' + window.location.hostname + '/oidc/afterlogoff.html',
    silent_redirect_uri: 'https://' + window.location.hostname + '/oidc/silent.html',
    acr_values: 'tenant:' + window.location.hostname,
    monitorSession: false
  };

  if (sessionStorage.getItem('oidc-disable-checksession') === null) {
    config.checkSessionInterval = 2000;
    config.monitorSession = true;
  }

  return config;
};
