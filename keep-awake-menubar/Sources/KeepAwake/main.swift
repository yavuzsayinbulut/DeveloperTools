import AppKit
import Foundation

@MainActor
final class CaffeinateController {
    private var process: Process?

    var isEnabled: Bool {
        process?.isRunning == true
    }

    func start() {
        guard !isEnabled else { return }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/caffeinate")
        process.arguments = ["-dims"]

        do {
            try process.run()
            self.process = process
        } catch {
            NSAlert(error: error).runModal()
        }
    }

    func stop() {
        process?.terminate()
        process = nil
    }

    func toggle() {
        isEnabled ? stop() : start()
    }
}

@MainActor
final class MouseMoverController {
    private let movementInterval: TimeInterval = 10
    private let movementDistance: CGFloat = 4

    private var timer: Timer?
    private var direction: CGFloat = 1

    var onStateChange: (() -> Void)?

    var isMoving: Bool {
        timer != nil
    }

    func start() {
        guard !isMoving else { return }

        direction = 1
        nudgeMouse()

        let timer = Timer.scheduledTimer(withTimeInterval: movementInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.handleTimerFired()
            }
        }
        RunLoop.main.add(timer, forMode: .common)
        self.timer = timer
        onStateChange?()
    }

    func stop() {
        timer?.invalidate()
        timer = nil
        onStateChange?()
    }

    func toggle() {
        isMoving ? stop() : start()
    }

    private func handleTimerFired() {
        nudgeMouse()
        onStateChange?()
    }

    private func nudgeMouse() {
        guard let event = CGEvent(source: nil) else { return }

        let currentLocation = event.location
        let nextLocation = CGPoint(
            x: currentLocation.x + (movementDistance * direction),
            y: currentLocation.y
        )

        CGWarpMouseCursorPosition(nextLocation)
        direction *= -1
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let caffeinateController = CaffeinateController()
    private let mouseMoverController = MouseMoverController()
    private let toggleItem = NSMenuItem(title: "Keep Screen Awake", action: #selector(toggleAwake), keyEquivalent: "")
    private let awakeDetailsItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    private let moveMouseItem = NSMenuItem(title: "Keep Mouse Moving", action: #selector(toggleMouseMovement), keyEquivalent: "")
    private let mouseDetailsItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        mouseMoverController.onStateChange = { [weak self] in
            self?.updateUI()
        }
        configureMenu()
        caffeinateController.start()
        mouseMoverController.start()
        updateUI()
    }

    func applicationWillTerminate(_ notification: Notification) {
        caffeinateController.stop()
        mouseMoverController.stop()
    }

    private func configureMenu() {
        guard let button = statusItem.button else { return }

        if let image = NSImage(systemSymbolName: "display", accessibilityDescription: "Keep Awake") {
            image.isTemplate = true
            button.image = image
        } else {
            button.title = "Awake"
        }

        let menu = NSMenu()

        toggleItem.target = self
        menu.addItem(toggleItem)

        awakeDetailsItem.isEnabled = false
        menu.addItem(awakeDetailsItem)

        moveMouseItem.target = self
        menu.addItem(moveMouseItem)

        mouseDetailsItem.isEnabled = false
        menu.addItem(mouseDetailsItem)
        menu.addItem(.separator())

        let quitItem = NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    private func updateUI() {
        let enabled = caffeinateController.isEnabled
        let isMoving = mouseMoverController.isMoving

        toggleItem.state = enabled ? .on : .off
        awakeDetailsItem.title = enabled ? "Keep Awake: Active" : "Keep Awake: Inactive"

        moveMouseItem.title = isMoving ? "Stop Mouse Movement" : "Start Mouse Movement"
        moveMouseItem.state = isMoving ? .on : .off
        mouseDetailsItem.title = isMoving ? "Mouse: Moving every 10 seconds" : "Mouse: Idle"

        guard let button = statusItem.button else { return }
        button.toolTip = tooltipText(isAwake: enabled, isMoving: isMoving)

        if button.image == nil {
            button.title = (enabled || isMoving) ? "Keep Awake On" : "Keep Awake Off"
        }
    }

    private func tooltipText(isAwake: Bool, isMoving: Bool) -> String {
        let awakeText = isAwake ? "active" : "inactive"
        let mouseText = isMoving ? "moving mouse" : "mouse idle"
        return "Keep Awake is \(awakeText), \(mouseText)"
    }

    @objc private func toggleAwake() {
        caffeinateController.toggle()
        updateUI()
    }

    @objc private func toggleMouseMovement() {
        mouseMoverController.toggle()
        updateUI()
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}

@main
@MainActor
struct KeepAwakeApp {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}
