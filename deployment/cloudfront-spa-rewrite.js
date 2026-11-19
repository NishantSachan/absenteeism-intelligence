// CloudFront Function (runtime cloudfront-js-2.0), attach to the DEFAULT behavior only, event type "Viewer request".
// Makes React Router deep links (e.g. /predict) work: any path without a file extension is served index.html.
// /api/* has its own behavior, so API 403/404 responses are never rewritten into HTML.
function handler(event) {
  var request = event.request;
  var uri = request.uri;
  if (uri.indexOf('/api/') === 0) { return request; }
  if (uri.indexOf('.') === -1) { request.uri = '/index.html'; }
  return request;
}
