import path from 'path';
import { defineConfig } from 'vite';
import tailwindcss from "@tailwindcss/vite"
import react from '@vitejs/plugin-react'
import proxyOptions from './proxyOptions';

// https://vitejs.dev/config/
export default defineConfig({
	plugins: [react(), tailwindcss()],
	server: {
		port: 8080,
		host: '0.0.0.0',
		proxy: proxyOptions
	},
	resolve: {
		alias: {
			'@': path.resolve(__dirname, './src')
		}
	},
	build: {
		outDir: '../mint/public/mint',
		emptyOutDir: true,
		target: 'es2015',
		//// Neoffice — added (upstream has no rollupOptions). We build the SPA in GitHub
		//// Actions (build-frontend.yml), outside a frappe-bench, where
		//// ../../../sites/common_site_config.json and ../../../frappe/ do not exist; without
		//// these externals rollup fails to resolve them and the build dies. Harmless in a bench.
		rollupOptions: {
			// Ignore Frappe bench-specific imports that don't exist in standalone builds
			external: [
				/common_site_config\.json/,
				/\.\.\/\.\.\/\.\.\/frappe\//,
			],
		},
	},
});
