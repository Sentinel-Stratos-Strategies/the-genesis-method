import SwiftUI
import WebKit
#if os(macOS)
import AppKit
#endif

struct WebDashboardView: View {
    @ObservedObject var backend: PythonBackend
    @ObservedObject var pluginRegistry: GenesisPluginRegistry

    var body: some View {
        HSplitView {
            GenesisCoverageSidebar(
                backend: backend,
                registry: pluginRegistry,
                reload: pluginRegistry.reload
            )
            .frame(minWidth: 300, idealWidth: 340, maxWidth: 420)

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
                    ProgressView("Starting forensic console...")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }
        .onAppear {
            backend.start()
            pluginRegistry.reload()
        }
#if os(macOS)
        .onReceive(NotificationCenter.default.publisher(for: NSApplication.willTerminateNotification)) { _ in
            backend.stop()
        }
#endif
    }
}

struct GenesisCoverageSidebar: View {
    @ObservedObject var backend: PythonBackend
    @ObservedObject var registry: GenesisPluginRegistry
    let reload: () -> Void

    private var snapshot: GenesisPluginSnapshot {
        registry.snapshot
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            header
            coverageMetrics
            pluginGroups(title: "Coverage", groups: snapshot.categories, limit: 9)
            pluginGroups(title: "Sources", groups: snapshot.sources, limit: 4)
            quickActions
            Spacer(minLength: 0)
            footer
        }
        .padding(16)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: "shield.lefthalf.filled")
                    .font(.title2)
                    .foregroundStyle(.blue)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Genesis Control")
                        .font(.headline)
                    Text(backend.serverReady ? "Dashboard online" : "Backend starting")
                        .font(.caption)
                        .foregroundStyle(backend.serverReady ? .green : .secondary)
                }
                Spacer()
                Button(action: reload) {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .disabled(registry.isLoading)
                .help("Reload plugin registry")
            }

            Text(registry.status)
                .font(.caption)
                .foregroundColor(registry.lastError == nil ? Color.secondary : Color.red)
                .lineLimit(3)
        }
    }

    private var coverageMetrics: some View {
        Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 10) {
            GridRow {
                MetricTile(title: "Plugins", value: "\(snapshot.totalCount)", symbol: "square.grid.3x3")
                MetricTile(title: "Enabled", value: "\(snapshot.defaultEnabledCount)", symbol: "bolt.badge.checkmark")
            }
            GridRow {
                MetricTile(title: "Manifest", value: "\(snapshot.manifestCount)", symbol: "doc.text")
                MetricTile(title: "Python", value: "\(snapshot.pythonCount)", symbol: "terminal")
            }
        }
    }

    private func pluginGroups(title: String, groups: [(name: String, count: Int)], limit: Int) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.subheadline.bold())

            if groups.isEmpty {
                Text("Waiting for registry data.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(groups.prefix(limit), id: \.name) { group in
                    HStack(spacing: 8) {
                        Text(group.name)
                            .font(.caption)
                            .lineLimit(1)
                        Spacer()
                        Text("\(group.count)")
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Root")
                .font(.caption.bold())
            Text(snapshot.root)
                .font(.caption2.monospaced())
                .foregroundStyle(.secondary)
                .lineLimit(3)
        }
    }

    private var quickActions: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Case Paths")
                .font(.subheadline.bold())

            QuickActionButton(title: "Open Evidence Input", subtitle: GenesisPaths.evidenceInputRoot, symbol: "externaldrive.fill") {
                openPath(GenesisPaths.evidenceInputRoot)
            }

            QuickActionButton(title: "Open Output Runs", subtitle: GenesisPaths.evidenceOutputRoot, symbol: "folder.fill") {
                openPath(GenesisPaths.evidenceOutputRoot)
            }

            QuickActionButton(title: "Open Action Log", subtitle: GenesisPaths.webActionLog, symbol: "doc.text.fill") {
                openPath(GenesisPaths.webActionLog)
            }
        }
    }

    private func openPath(_ path: String) {
#if os(macOS)
        let url = URL(fileURLWithPath: path)
        NSWorkspace.shared.open(url)
#endif
    }
}

struct MetricTile: View {
    let title: String
    let value: String
    let symbol: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Image(systemName: symbol)
                .foregroundStyle(.blue)
            Text(value)
                .font(.title3.monospacedDigit().bold())
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

struct QuickActionButton: View {
    let title: String
    let subtitle: String
    let symbol: String
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .foregroundStyle(.blue)
                    .frame(width: 18)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.caption.bold())
                    Text(subtitle)
                        .font(.caption2.monospaced())
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Spacer()
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .padding(9)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .help(subtitle)
    }
}

struct GenesisWebView: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.defaultWebpagePreferences.allowsContentJavaScript = true
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
