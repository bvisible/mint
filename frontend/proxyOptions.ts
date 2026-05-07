// Dev-only: read webserver_port from the bench's common_site_config.json
// when running in a frappe-bench checkout. In production builds (CI) the
// file is absent, so fall back to the default webserver port.
let webserver_port = 8000;
try {
	// eslint-disable-next-line @typescript-eslint/no-var-requires
	const cfg = require('../../../sites/common_site_config.json');
	webserver_port = cfg.webserver_port || webserver_port;
} catch {
	// fall back to default 8000
}

export default {
	'^/(app|api|assets|files|private)': {
		target: `http://127.0.0.1:${webserver_port}`,
		ws: true,
		router: function(req) {
			const site_name = req.headers.host.split(':')[0];
			return `http://${site_name}:${webserver_port}`;
		}
	}
};
