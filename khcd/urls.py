"""Canonical /camdo URLs, with safe compatibility for existing links and open forms."""
from flask import redirect, request, url_for


def install_legacy_urls(app):
    for rule in list(app.url_map.iter_rules()):
        if not rule.rule.startswith('/camdo/'):
            continue
        if rule.rule.startswith('/camdo/lap-phieu'):
            old = rule.rule.replace('/camdo/lap-phieu', '/cam-do', 1)
        else:
            old = rule.rule[len('/camdo'):]
        # Same endpoint preserves auth, CSRF, upload policy and POST behavior.
        # Canonical rules were registered first, so url_for always builds new URLs.
        app.add_url_rule(old, endpoint=rule.endpoint, view_func=app.view_functions[rule.endpoint],
                         methods=rule.methods, defaults=rule.defaults)
    app.add_url_rule('/phieu-cam-do/moi', endpoint='web.pawn_new',
                     view_func=app.view_functions['web.pawn_new'], methods=['GET', 'POST'])
    app.add_url_rule('/camdo/', endpoint='web.dashboard', view_func=app.view_functions['web.dashboard'])

    @app.before_request
    def canonical_url():
        if request.method not in ('GET', 'HEAD') or not request.url_rule or request.path == '/':
            return
        if request.endpoint.startswith(('web.', 'customer_popup.', 'loans.', 'giaodich.')):
            destination = url_for(request.endpoint, **(request.view_args or {}))
            if destination != request.path and destination.startswith('/camdo'):
                # Preserve the original encoded query, including repeated filters.
                if request.query_string:
                    destination += '?' + request.query_string.decode('ascii')
                return redirect(destination, code=308)
