import SwiftUI
import WebKit

struct WebDashboardView: View {
    @ObservedObject var backend: PythonBackend

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("The Genesis Method")
                    .font(.title2.bold())
                Spacer()
                Text(backend.status)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 12)
            .padding(.top, 8)

            if backend.serverReady {
                GenesisWebView(url: backend.dashboardURL)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                ProgressView("Starting forensic console…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .onAppear { backend.start() }
        .onDisappear { backend.stop() }
    }
}

struct GenesisWebView: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.preferences.javaScriptEnabled = true
        let web = WKWebView(frame: .zero, configuration: config)
        web.load(URLRequest(url: url))
        return web
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {
        if nsView.url != url {
            nsView.load(URLRequest(url: url))
        }
    }
}
