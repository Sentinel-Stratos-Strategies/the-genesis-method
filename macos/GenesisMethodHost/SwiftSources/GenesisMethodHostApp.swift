import SwiftUI

@main
struct GenesisMethodHostApp: App {
    @StateObject private var backend = PythonBackend()

    var body: some Scene {
        WindowGroup {
            WebDashboardView(backend: backend)
                .frame(minWidth: 1100, minHeight: 820)
        }
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}
