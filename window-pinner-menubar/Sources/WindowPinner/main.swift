import AppKit
import ApplicationServices
import CoreGraphics
import Foundation

private typealias CGSConnectionID = UInt32

@_silgen_name("CGSMainConnectionID")
private func CGSMainConnectionID() -> CGSConnectionID

@_silgen_name("CGSSetWindowLevel")
@discardableResult
private func CGSSetWindowLevel(
    _ connectionID: CGSConnectionID,
    _ windowID: CGWindowID,
    _ level: Int32
) -> Int32

@_silgen_name("CGSOrderWindow")
@discardableResult
private func CGSOrderWindow(
    _ connectionID: CGSConnectionID,
    _ windowID: CGWindowID,
    _ place: Int32,
    _ relativeToWindow: CGWindowID
) -> Int32

private struct KeyboardShortcut {
    let keyCode: UInt16
    let modifiers: NSEvent.ModifierFlags
    let displayText: String
}

private struct WindowSnapshot {
    let appName: String
    let title: String
    let pid: pid_t
    let windowID: CGWindowID
    let axWindow: AXUIElement
    let originalLevel: Int32
}

private enum WindowPinError: LocalizedError {
    case accessibilityDenied
    case noFrontmostApp
    case noUsableWindow
    case unsupportedWindow
    case setLevelFailed(Int32)

    var errorDescription: String? {
        switch self {
        case .accessibilityDenied:
            return "WindowPinner icin Accessibility izni gerekli."
        case .noFrontmostApp:
            return "Aktif bir uygulama bulunamadi."
        case .noUsableWindow:
            return "Aktif pencere bulunamadi."
        case .unsupportedWindow:
            return "Bu pencere WindowServer uzerinden eslestirilemedi."
        case .setLevelFailed(let code):
            return "Pencere seviyesi degistirilemedi (kod: \(code))."
        }
    }
}

@MainActor
private enum PermissionManager {
    static func isTrusted() -> Bool {
        AXIsProcessTrusted()
    }

    static func openAccessibilitySettings() {
        guard
            let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility")
        else {
            return
        }
        NSWorkspace.shared.open(url)
    }
}

@MainActor
private final class WindowPinController {
    private static let pinnedLevel = Int32(CGWindowLevelForKey(.statusWindow))
    private static let orderAbove: Int32 = 1

    private let connectionID = CGSMainConnectionID()
    private var pinnedWindow: WindowSnapshot?
    private var healthTimer: Timer?
    private var lastExternalApplication: NSRunningApplication?

    var statusText: String {
        guard let pinnedWindow else {
            return "Pinned: Yok"
        }
        return "Pinned: \(pinnedWindow.appName) - \(pinnedWindow.title)"
    }

    var hasPinnedWindow: Bool {
        pinnedWindow != nil
    }

    func toggleFrontmostWindow() throws {
        let candidate = try snapshotFrontmostWindow()
        if let pinnedWindow, pinnedWindow.windowID == candidate.windowID {
            unpinCurrentWindow()
            return
        }
        try pin(snapshot: candidate)
    }

    func pinFrontmostWindow() throws {
        try pin(snapshot: snapshotFrontmostWindow())
    }

    func updateLastExternalApplication(_ application: NSRunningApplication) {
        let currentPID = ProcessInfo.processInfo.processIdentifier
        guard application.processIdentifier != currentPID else {
            return
        }
        lastExternalApplication = application
    }

    func unpinCurrentWindow() {
        guard let pinnedWindow else { return }
        restoreLevel(for: pinnedWindow)
        self.pinnedWindow = nil
        stopHealthCheck()
    }

    func refreshPinnedWindowState() {
        guard let pinnedWindow else { return }

        guard isProcessAlive(pinnedWindow.pid) else {
            self.pinnedWindow = nil
            stopHealthCheck()
            return
        }

        if currentWindowLevel(for: pinnedWindow.windowID) == nil {
            self.pinnedWindow = nil
            stopHealthCheck()
        }
    }

    private func pin(snapshot: WindowSnapshot) throws {
        if let existing = pinnedWindow {
            restoreLevel(for: existing)
        }

        try promote(snapshot)
        pinnedWindow = snapshot
        startHealthCheck()
    }

    private func restoreLevel(for snapshot: WindowSnapshot) {
        _ = CGSSetWindowLevel(connectionID, snapshot.windowID, snapshot.originalLevel)
    }

    private func startHealthCheck() {
        stopHealthCheck()
        healthTimer = Timer.scheduledTimer(
            withTimeInterval: 0.35,
            repeats: true
        ) { [weak self] _ in
            Task { @MainActor in
                self?.maintainPinnedWindow()
            }
        }
    }

    private func stopHealthCheck() {
        healthTimer?.invalidate()
        healthTimer = nil
    }

    private func maintainPinnedWindow() {
        guard let pinnedWindow else { return }

        guard isProcessAlive(pinnedWindow.pid) else {
            self.pinnedWindow = nil
            stopHealthCheck()
            return
        }

        guard currentWindowLevel(for: pinnedWindow.windowID) != nil else {
            self.pinnedWindow = nil
            stopHealthCheck()
            return
        }

        try? promote(pinnedWindow)
    }

    private func snapshotFrontmostWindow() throws -> WindowSnapshot {
        guard PermissionManager.isTrusted() else {
            throw WindowPinError.accessibilityDenied
        }

        guard let app = activeExternalApplication() else {
            throw WindowPinError.noFrontmostApp
        }

        let axApp = AXUIElementCreateApplication(app.processIdentifier)
        let axWindow = try copyWindow(from: axApp)
        let frame = try copyFrame(from: axWindow)
        let windowID = try matchWindowID(pid: app.processIdentifier, frame: frame)
        let originalLevel = currentWindowLevel(for: windowID) ?? Int32(CGWindowLevelForKey(.normalWindow))
        let rawTitle = copyStringAttribute(kAXTitleAttribute as CFString, from: axWindow)
        let title = normalizedTitle(rawTitle, fallback: app.localizedName ?? "Adsiz pencere")

        return WindowSnapshot(
            appName: app.localizedName ?? "Unknown App",
            title: title,
            pid: app.processIdentifier,
            windowID: windowID,
            axWindow: axWindow,
            originalLevel: originalLevel
        )
    }

    private func activeExternalApplication() -> NSRunningApplication? {
        let currentPID = ProcessInfo.processInfo.processIdentifier
        guard let app = NSWorkspace.shared.frontmostApplication else {
            return lastExternalApplication
        }
        guard app.processIdentifier != currentPID else {
            if let lastExternalApplication, !lastExternalApplication.isTerminated {
                return lastExternalApplication
            }
            return NSWorkspace.shared.runningApplications.first {
                $0.isActive && $0.processIdentifier != currentPID
            }
        }
        return app
    }

    private func copyWindow(from appElement: AXUIElement) throws -> AXUIElement {
        if let focusedWindow = copyElementAttribute(kAXFocusedWindowAttribute as CFString, from: appElement) {
            return focusedWindow
        }
        if let mainWindow = copyElementAttribute(kAXMainWindowAttribute as CFString, from: appElement) {
            return mainWindow
        }
        throw WindowPinError.noUsableWindow
    }

    private func copyFrame(from window: AXUIElement) throws -> CGRect {
        guard
            let position = copyPointAttribute(kAXPositionAttribute as CFString, from: window),
            let size = copySizeAttribute(kAXSizeAttribute as CFString, from: window)
        else {
            throw WindowPinError.noUsableWindow
        }
        return CGRect(origin: position, size: size)
    }

    private func matchWindowID(pid: pid_t, frame: CGRect) throws -> CGWindowID {
        let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
        guard let rawList = CGWindowListCopyWindowInfo(options, kCGNullWindowID) as? [[String: Any]] else {
            throw WindowPinError.unsupportedWindow
        }

        var bestMatch: (windowID: CGWindowID, score: CGFloat)?

        for info in rawList {
            guard let ownerPID = (info[kCGWindowOwnerPID as String] as? NSNumber)?.int32Value else {
                continue
            }
            guard ownerPID == pid else {
                continue
            }

            guard let boundsDict = info[kCGWindowBounds as String] as? NSDictionary else {
                continue
            }
            guard let bounds = CGRect(dictionaryRepresentation: boundsDict) else {
                continue
            }

            let score = frameDistance(lhs: frame, rhs: bounds)
            guard let windowNumber = (info[kCGWindowNumber as String] as? NSNumber)?.uint32Value else {
                continue
            }

            if bestMatch == nil || score < bestMatch!.score {
                bestMatch = (windowNumber, score)
            }
        }

        guard let bestMatch else {
            throw WindowPinError.unsupportedWindow
        }

        return bestMatch.windowID
    }

    private func currentWindowLevel(for windowID: CGWindowID) -> Int32? {
        guard
            let rawList = CGWindowListCopyWindowInfo(.optionIncludingWindow, windowID) as? [[String: Any]],
            let info = rawList.first,
            let layer = (info[kCGWindowLayer as String] as? NSNumber)?.int32Value
        else {
            return nil
        }
        return layer
    }

    private func promote(_ snapshot: WindowSnapshot) throws {
        let setLevelResult = CGSSetWindowLevel(
            connectionID,
            snapshot.windowID,
            Self.pinnedLevel
        )
        guard setLevelResult == 0 else {
            throw WindowPinError.setLevelFailed(setLevelResult)
        }

        _ = CGSOrderWindow(
            connectionID,
            snapshot.windowID,
            Self.orderAbove,
            kCGNullWindowID
        )
    }

    private func frameDistance(lhs: CGRect, rhs: CGRect) -> CGFloat {
        let dx = abs(lhs.origin.x - rhs.origin.x)
        let dy = abs(lhs.origin.y - rhs.origin.y)
        let dw = abs(lhs.size.width - rhs.size.width)
        let dh = abs(lhs.size.height - rhs.size.height)
        return dx + dy + dw + dh
    }

    private func normalizedTitle(_ rawTitle: String?, fallback: String) -> String {
        let trimmed = rawTitle?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return trimmed.isEmpty ? fallback : trimmed
    }

    private func copyElementAttribute(_ attribute: CFString, from element: AXUIElement) -> AXUIElement? {
        var value: CFTypeRef?
        let error = AXUIElementCopyAttributeValue(element, attribute, &value)
        guard error == .success, let value else {
            return nil
        }
        return (value as! AXUIElement)
    }

    private func copyStringAttribute(_ attribute: CFString, from element: AXUIElement) -> String? {
        var value: CFTypeRef?
        let error = AXUIElementCopyAttributeValue(element, attribute, &value)
        guard error == .success else {
            return nil
        }
        return value as? String
    }

    private func copyPointAttribute(_ attribute: CFString, from element: AXUIElement) -> CGPoint? {
        var value: CFTypeRef?
        let error = AXUIElementCopyAttributeValue(element, attribute, &value)
        guard error == .success, let value else {
            return nil
        }
        guard CFGetTypeID(value) == AXValueGetTypeID() else {
            return nil
        }

        var point = CGPoint.zero
        let axValue = value as! AXValue
        guard AXValueGetType(axValue) == .cgPoint, AXValueGetValue(axValue, .cgPoint, &point) else {
            return nil
        }
        return point
    }

    private func copySizeAttribute(_ attribute: CFString, from element: AXUIElement) -> CGSize? {
        var value: CFTypeRef?
        let error = AXUIElementCopyAttributeValue(element, attribute, &value)
        guard error == .success, let value else {
            return nil
        }
        guard CFGetTypeID(value) == AXValueGetTypeID() else {
            return nil
        }

        var size = CGSize.zero
        let axValue = value as! AXValue
        guard AXValueGetType(axValue) == .cgSize, AXValueGetValue(axValue, .cgSize, &size) else {
            return nil
        }
        return size
    }

    private func isProcessAlive(_ pid: pid_t) -> Bool {
        kill(pid, 0) == 0 || errno != ESRCH
    }
}

@MainActor
private final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let controller = WindowPinController()
    private let pinShortcut = KeyboardShortcut(
        keyCode: 35,
        modifiers: [.control, .option, .command],
        displayText: "Control + Option + Command + P"
    )
    private let unpinShortcut = KeyboardShortcut(
        keyCode: 32,
        modifiers: [.control, .option, .command],
        displayText: "Control + Option + Command + U"
    )

    private var globalMonitor: Any?
    private var localMonitor: Any?

    private let menu = NSMenu()
    private let pinItem = NSMenuItem(title: "", action: #selector(pinFrontWindow), keyEquivalent: "")
    private let unpinItem = NSMenuItem(title: "", action: #selector(unpinWindow), keyEquivalent: "")
    private let statusLabelItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    private let permissionLabelItem = NSMenuItem(title: "", action: nil, keyEquivalent: "")
    private let permissionsItem = NSMenuItem(title: "Open Accessibility Settings", action: #selector(openAccessibilitySettings), keyEquivalent: "")
    private let quitItem = NSMenuItem(title: "Quit", action: #selector(quit), keyEquivalent: "q")

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        configureMenu()
        observeWorkspaceChanges()
        installHotkeyMonitors()
        promptForPermissionsIfNeeded()
        updateMenuState()
    }

    func applicationWillTerminate(_ notification: Notification) {
        controller.unpinCurrentWindow()
        removeHotkeyMonitors()
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        updateMenuState()
    }

    private func configureMenu() {
        guard let button = statusItem.button else { return }

        if let image = NSImage(systemSymbolName: "pin.fill", accessibilityDescription: "Window Pinner") {
            image.isTemplate = true
            button.image = image
        } else {
            button.title = "Pin"
        }
        button.toolTip = "WindowPinner"

        pinItem.target = self
        unpinItem.target = self
        permissionsItem.target = self
        quitItem.target = self

        statusLabelItem.isEnabled = false
        permissionLabelItem.isEnabled = false

        menu.delegate = self
        menu.addItem(pinItem)
        menu.addItem(unpinItem)
        menu.addItem(.separator())
        menu.addItem(statusLabelItem)
        menu.addItem(permissionLabelItem)
        menu.addItem(.separator())
        menu.addItem(permissionsItem)
        menu.addItem(.separator())
        menu.addItem(quitItem)
        statusItem.menu = menu
    }

    private func installHotkeyMonitors() {
        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { [weak self] event in
            Task { @MainActor in
                self?.handleKeyEvent(event)
            }
        }

        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            Task { @MainActor in
                self?.handleKeyEvent(event)
            }
            return event
        }
    }

    private func observeWorkspaceChanges() {
        NSWorkspace.shared.notificationCenter.addObserver(
            self,
            selector: #selector(handleWorkspaceActivation(_:)),
            name: NSWorkspace.didActivateApplicationNotification,
            object: nil
        )
    }

    private func removeHotkeyMonitors() {
        if let globalMonitor {
            NSEvent.removeMonitor(globalMonitor)
            self.globalMonitor = nil
        }
        if let localMonitor {
            NSEvent.removeMonitor(localMonitor)
            self.localMonitor = nil
        }
    }

    private func handleKeyEvent(_ event: NSEvent) {
        guard !event.isARepeat else { return }

        if matches(pinShortcut, event: event) {
            executeShortcut {
                try controller.toggleFrontmostWindow()
            }
            return
        }

        if matches(unpinShortcut, event: event) {
            controller.unpinCurrentWindow()
            updateMenuState()
        }
    }

    private func matches(_ shortcut: KeyboardShortcut, event: NSEvent) -> Bool {
        let relevantFlags = event.modifierFlags.intersection([.shift, .control, .option, .command])
        return event.keyCode == shortcut.keyCode && relevantFlags == shortcut.modifiers
    }

    private func executeShortcut(_ block: () throws -> Void) {
        do {
            try block()
        } catch {
            presentError(error)
        }
        updateMenuState()
    }

    private func updateMenuState() {
        pinItem.title = "Pin / Toggle Front Window (\(pinShortcut.displayText))"
        unpinItem.title = "Unpin Current Window (\(unpinShortcut.displayText))"
        unpinItem.isEnabled = controller.hasPinnedWindow
        statusLabelItem.title = controller.statusText

        let permissionGranted = PermissionManager.isTrusted()
        permissionLabelItem.title = permissionGranted ? "Accessibility: Hazir" : "Accessibility: Izin gerekiyor"

        guard let button = statusItem.button else { return }
        button.toolTip = controller.hasPinnedWindow ? controller.statusText : "WindowPinner"

        if let image = button.image {
            image.isTemplate = true
            button.contentTintColor = controller.hasPinnedWindow ? .systemRed : nil
        }
    }

    @objc private func handleWorkspaceActivation(_ notification: Notification) {
        guard
            let application = notification.userInfo?[NSWorkspace.applicationUserInfoKey] as? NSRunningApplication
        else {
            return
        }

        controller.updateLastExternalApplication(application)
        updateMenuState()
    }

    private func promptForPermissionsIfNeeded() {
        guard !PermissionManager.isTrusted() else {
            return
        }

        NSApp.activate(ignoringOtherApps: true)

        let alert = NSAlert()
        alert.messageText = "Accessibility izni gerekiyor"
        alert.informativeText = """
        WindowPinner aktif pencereyi pinlemek icin Accessibility iznine ihtiyac duyar.

        1. System Settings > Privacy & Security > Accessibility ekranini ac
        2. WindowPinner'i etkinlestir
        3. Sonra hedef pencereye gecip \(pinShortcut.displayText) tuslarina bas
        """
        alert.addButton(withTitle: "Ayarlari Ac")
        alert.addButton(withTitle: "Daha Sonra")

        if alert.runModal() == .alertFirstButtonReturn {
            PermissionManager.openAccessibilitySettings()
        }
    }

    private func presentError(_ error: Error) {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "WindowPinner"
        alert.informativeText = error.localizedDescription
        alert.runModal()
    }

    @objc private func pinFrontWindow() {
        executeShortcut {
            try controller.pinFrontmostWindow()
        }
    }

    @objc private func unpinWindow() {
        controller.unpinCurrentWindow()
        updateMenuState()
    }

    @objc private func openAccessibilitySettings() {
        PermissionManager.openAccessibilitySettings()
    }

    @objc private func quit() {
        NSApp.terminate(nil)
    }
}

@main
@MainActor
private struct WindowPinnerApp {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.run()
    }
}
