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
enum MouseMovementSpeed: String, CaseIterable {
    case slow
    case normal
    case fast

    var interval: TimeInterval {
        switch self {
        case .slow:
            return 10
        case .normal:
            return 3
        case .fast:
            return 1
        }
    }

    var menuTitle: String {
        switch self {
        case .slow:
            return "Slow - every 10 seconds"
        case .normal:
            return "Normal - every 3 seconds"
        case .fast:
            return "Fast - every second"
        }
    }

    var detailText: String {
        switch self {
        case .slow:
            return "every 10 seconds"
        case .normal:
            return "every 3 seconds"
        case .fast:
            return "every second"
        }
    }
}

@MainActor
final class MouseMoverController {
    private let screenPadding: CGFloat = 32

    private var timer: Timer?

    var onStateChange: (() -> Void)?
    private(set) var speed: MouseMovementSpeed = .normal

    var isMoving: Bool {
        timer != nil
    }

    func start() {
        guard !isMoving else { return }

        moveMouse()
        scheduleTimer()
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

    func setSpeed(_ speed: MouseMovementSpeed) {
        guard self.speed != speed else { return }

        self.speed = speed

        if isMoving {
            timer?.invalidate()
            scheduleTimer()
        }

        onStateChange?()
    }

    private func scheduleTimer() {
        let timer = Timer(timeInterval: speed.interval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                self?.handleTimerFired()
            }
        }
        RunLoop.main.add(timer, forMode: .common)
        self.timer = timer
    }

    private func handleTimerFired() {
        moveMouse()
        onStateChange?()
    }

    private func moveMouse() {
        guard let event = CGEvent(source: nil) else { return }

        let currentLocation = event.location
        let nextLocation = randomDistantLocation(from: currentLocation)

        CGWarpMouseCursorPosition(nextLocation)
    }

    private func randomDistantLocation(from currentLocation: CGPoint) -> CGPoint {
        let displayBounds = activeDisplayBounds()
        guard !displayBounds.isEmpty else { return currentLocation }

        let minimumDistance = minimumMovementDistance(for: displayBounds)

        for _ in 0..<24 {
            guard
                let displayBounds = displayBounds.randomElement(),
                let point = randomPoint(in: displayBounds)
            else {
                continue
            }

            if distance(from: currentLocation, to: point) >= minimumDistance {
                return point
            }
        }

        return randomPoint(in: displayBounds.randomElement() ?? displayBounds[0]) ?? currentLocation
    }

    private func activeDisplayBounds() -> [CGRect] {
        var displayCount: UInt32 = 0
        guard CGGetActiveDisplayList(0, nil, &displayCount) == .success, displayCount > 0 else {
            return []
        }

        var displays = [CGDirectDisplayID](repeating: 0, count: Int(displayCount))
        guard CGGetActiveDisplayList(displayCount, &displays, &displayCount) == .success else {
            return []
        }

        return displays.prefix(Int(displayCount))
            .map { CGDisplayBounds($0) }
            .filter { !$0.isEmpty }
    }

    private func randomPoint(in bounds: CGRect) -> CGPoint? {
        let horizontalPadding = min(screenPadding, max(0, bounds.width / 4))
        let verticalPadding = min(screenPadding, max(0, bounds.height / 4))
        let safeBounds = bounds.insetBy(dx: horizontalPadding, dy: verticalPadding)

        guard safeBounds.width > 0, safeBounds.height > 0 else { return nil }

        return CGPoint(
            x: CGFloat.random(in: safeBounds.minX...safeBounds.maxX),
            y: CGFloat.random(in: safeBounds.minY...safeBounds.maxY)
        )
    }

    private func minimumMovementDistance(for displayBounds: [CGRect]) -> CGFloat {
        let largestSpan = displayBounds
            .map { max($0.width, $0.height) }
            .max() ?? 0

        return max(240, largestSpan * 0.35)
    }

    private func distance(from firstPoint: CGPoint, to secondPoint: CGPoint) -> CGFloat {
        hypot(firstPoint.x - secondPoint.x, firstPoint.y - secondPoint.y)
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let caffeinateController = CaffeinateController()
    private let mouseMoverController = MouseMoverController()
    private let toggleItem = NSMenuItem(title: "Display Session", action: #selector(toggleDisplaySession), keyEquivalent: "")
    private let displaySessionDetailsItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    private let moveMouseItem = NSMenuItem(title: "Input Activity", action: #selector(toggleMouseMovement), keyEquivalent: "")
    private let mouseDetailsItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    private let mouseSpeedItem = NSMenuItem(title: "Activity Rate", action: nil, keyEquivalent: "")
    private let closedLidDetailsItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    private var mouseSpeedItems: [MouseMovementSpeed: NSMenuItem] = [:]

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

        if let image = NSImage(systemSymbolName: "display", accessibilityDescription: "Display Agent") {
            image.isTemplate = true
            button.image = image
        } else {
            button.title = "Display"
        }

        let menu = NSMenu()

        toggleItem.target = self
        menu.addItem(toggleItem)

        displaySessionDetailsItem.isEnabled = false
        menu.addItem(displaySessionDetailsItem)

        moveMouseItem.target = self
        menu.addItem(moveMouseItem)

        mouseDetailsItem.isEnabled = false
        menu.addItem(mouseDetailsItem)

        let mouseSpeedMenu = NSMenu()
        for speed in MouseMovementSpeed.allCases {
            let speedItem = NSMenuItem(title: speed.menuTitle, action: #selector(selectMouseSpeed), keyEquivalent: "")
            speedItem.target = self
            speedItem.representedObject = speed.rawValue
            mouseSpeedMenu.addItem(speedItem)
            mouseSpeedItems[speed] = speedItem
        }
        mouseSpeedItem.submenu = mouseSpeedMenu
        menu.addItem(mouseSpeedItem)

        closedLidDetailsItem.isEnabled = false
        menu.addItem(closedLidDetailsItem)
        menu.addItem(.separator())

        let quitItem = NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q")
        quitItem.target = self
        menu.addItem(quitItem)

        statusItem.menu = menu
    }

    private func updateUI() {
        let enabled = caffeinateController.isEnabled
        let isMoving = mouseMoverController.isMoving
        let mouseSpeed = mouseMoverController.speed

        toggleItem.state = enabled ? .on : .off
        displaySessionDetailsItem.title = enabled ? "Display Session: Active" : "Display Session: Inactive"

        moveMouseItem.title = isMoving ? "Stop Input Activity" : "Start Input Activity"
        moveMouseItem.state = isMoving ? .on : .off
        mouseDetailsItem.title = isMoving ? "Input: Active \(mouseSpeed.detailText)" : "Input: Idle"
        for speed in MouseMovementSpeed.allCases {
            mouseSpeedItems[speed]?.state = speed == mouseSpeed ? .on : .off
        }
        closedLidDetailsItem.title = "Closed Lid: Needs AC + external display + keyboard/mouse"

        guard let button = statusItem.button else { return }
        button.toolTip = tooltipText(isSessionActive: enabled, isMoving: isMoving, mouseSpeed: mouseSpeed)

        if button.image == nil {
            button.title = (enabled || isMoving) ? "Display Agent On" : "Display Agent Off"
        }
    }

    private func tooltipText(isSessionActive: Bool, isMoving: Bool, mouseSpeed: MouseMovementSpeed) -> String {
        let sessionText = isSessionActive ? "active" : "inactive"
        let inputText = isMoving ? "input active \(mouseSpeed.detailText)" : "input idle"
        return "Display session is \(sessionText), \(inputText). Closed lid needs AC power, external display, and external input."
    }

    @objc private func toggleDisplaySession() {
        caffeinateController.toggle()
        updateUI()
    }

    @objc private func toggleMouseMovement() {
        mouseMoverController.toggle()
        updateUI()
    }

    @objc private func selectMouseSpeed(_ sender: NSMenuItem) {
        guard
            let rawValue = sender.representedObject as? String,
            let speed = MouseMovementSpeed(rawValue: rawValue)
        else {
            return
        }

        mouseMoverController.setSpeed(speed)
        updateUI()
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}

@main
@MainActor
struct DisplayAgentApp {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}
