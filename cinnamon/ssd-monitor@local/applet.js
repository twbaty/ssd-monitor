const Applet = imports.ui.applet;
const PopupMenu = imports.ui.popupMenu;
const Mainloop = imports.mainloop;
const GLib = imports.gi.GLib;
const ByteArray = imports.byteArray;

const HISTORY_DIR = GLib.build_filenamev([
    GLib.get_home_dir(), '.local', 'share', 'ssd-monitor'
]);
const SELECTED_DEVICE_FILE = GLib.build_filenamev([
    GLib.get_user_config_dir(), 'ssd-monitor-selected-device'
]);

function readText(path) {
    const [ok, bytes] = GLib.file_get_contents(path);
    return ok ? ByteArray.toString(bytes) : null;
}

function formatRate(bytesPerSecond) {
    if (bytesPerSecond === null) return '—';
    if (bytesPerSecond >= 1048576) return `${(bytesPerSecond / 1048576).toFixed(1)}M/s`;
    if (bytesPerSecond >= 1024) return `${(bytesPerSecond / 1024).toFixed(1)}K/s`;
    return `${Math.round(bytesPerSecond)}B/s`;
}

function valueOrDash(value, suffix = '') {
    return value === null || value === undefined ? '—' : `${value}${suffix}`;
}

class SSDMonitorApplet extends Applet.TextIconApplet {
    constructor(metadata, orientation, panelHeight, instanceId) {
        super(orientation, panelHeight, instanceId);
        this.setAllowedLayout(Applet.AllowedLayout.BOTH);
        this.set_applet_icon_symbolic_name('drive-harddisk-symbolic');
        this.set_applet_label('SSD ↓ — ↑ —');
        this.set_applet_tooltip('SSD Monitor: loading disk activity');

        this.menu = new Applet.AppletPopupMenu(this, orientation);
        this.menuManager = new PopupMenu.PopupMenuManager(this);
        this.menuManager.addMenu(this.menu);
        this._deviceMenu = new PopupMenu.PopupSubMenuMenuItem('Select drive');
        this.menu.addMenuItem(this._deviceMenu);
        this._rows = {};
        for (const key of ['drive', 'smart', 'lifetime', 'temperature', 'read', 'write',
                           'reallocated', 'uncorrectable', 'crc', 'recorded']) {
            const item = new PopupMenu.PopupMenuItem('');
            this.menu.addMenuItem(item);
            this._rows[key] = item;
        }
        try {
            this._selectedDevice = readText(SELECTED_DEVICE_FILE).trim();
        } catch (error) {
            this._selectedDevice = null;
        }
        this._previous = null;
        this._update();
        this._timer = Mainloop.timeout_add_seconds(2, () => {
            this._update();
            return true;
        });
    }

    _latestRecords() {
        let dir;
        try {
            dir = GLib.Dir.open(HISTORY_DIR, 0);
        } catch (error) {
            return [];
        }
        const names = [];
        let name;
        while ((name = dir.read_name()) !== null) {
            if (name.endsWith('.json')) names.push(name);
        }
        dir.close();
        names.sort();
        for (let index = names.length - 1; index >= 0; index--) {
            try {
                const records = JSON.parse(readText(GLib.build_filenamev([HISTORY_DIR, names[index]])));
                if (Array.isArray(records) && records.length > 0) return records;
            } catch (error) {
                // Ignore a partial or unrelated file and try the previous snapshot.
            }
        }
        return [];
    }

    _physicalDevices() {
        const devices = [];
        try {
            const dir = GLib.Dir.open('/sys/class/block', 0);
            let name;
            while ((name = dir.read_name()) !== null) {
                if (!/^(sd[a-z]+|nvme\d+n\d+|mmcblk\d+)$/.test(name)) continue;
                const path = `/sys/class/block/${name}`;
                if (GLib.file_test(`${path}/partition`, GLib.FileTest.EXISTS)) continue;
                let model = name;
                try { model = readText(`${path}/device/model`).trim(); } catch (error) { /* optional */ }
                devices.push({path: `/dev/${name}`, model});
            }
            dir.close();
        } catch (error) {
            return devices;
        }
        return devices.sort((a, b) => a.path.localeCompare(b.path));
    }

    _updateDeviceMenu(devices) {
        this._deviceMenu.menu.removeAll();
        if (!devices.length) {
            this._deviceMenu.menu.addMenuItem(new PopupMenu.PopupMenuItem('No physical drives found'));
            return;
        }
        for (const device of devices) {
            const selected = device.path === this._selectedDevice ? '✓ ' : '';
            const item = new PopupMenu.PopupMenuItem(`${selected}${device.path} · ${device.model}`);
            item.connect('activate', () => {
                this._selectedDevice = device.path;
                this._previous = null;
                try { GLib.file_set_contents(SELECTED_DEVICE_FILE, device.path); } catch (error) { global.logError(error); }
                this._update();
            });
            this._deviceMenu.menu.addMenuItem(item);
        }
    }

    _diskRates(devicePath) {
        if (!devicePath || !/^\/dev\/[a-zA-Z0-9_-]+$/.test(devicePath)) return [null, null];
        const name = devicePath.slice(5);
        try {
            const fields = readText(`/sys/class/block/${name}/stat`).trim().split(/\s+/).map(Number);
            const now = GLib.get_monotonic_time() / 1000000;
            if (fields.length < 7 || !Number.isFinite(fields[2]) || !Number.isFinite(fields[6])) {
                return [null, null];
            }
            const sample = {name, readSectors: fields[2], writeSectors: fields[6], time: now};
            const previous = this._previous;
            this._previous = sample;
            if (!previous || previous.name !== name || now <= previous.time) return [null, null];
            const elapsed = now - previous.time;
            return [Math.max(0, (sample.readSectors - previous.readSectors) * 512 / elapsed),
                    Math.max(0, (sample.writeSectors - previous.writeSectors) * 512 / elapsed)];
        } catch (error) {
            return [null, null];
        }
    }

    _setRow(key, text) {
        this._rows[key].label.set_text(text);
    }

    _update() {
        try {
            const records = this._latestRecords();
            const devices = this._physicalDevices();
            if (!this._selectedDevice) {
                this._selectedDevice = devices.find(item => item.path === '/dev/sda')?.path ||
                    devices[0]?.path || records[0]?.device?.path || null;
            }
            const device = this._selectedDevice;
            const connected = devices.some(item => item.path === device);
            const record = records.find(item => item.device?.path === device);
            const [read, write] = this._diskRates(device);
            const health = record?.health || {};
            const errors = record?.errors || {};
            const temperature = record?.temperature?.celsius;
            const lifetime = health.lifetime_remaining_percent;
            const timestamp = record?.collection?.timestamp_utc;
            const age = timestamp ? Date.now() - Date.parse(timestamp) : Infinity;
            const fresh = age >= 0 && age < 24 * 60 * 60 * 1000;
            const wear = fresh && lifetime !== null && lifetime !== undefined ? ` · ${lifetime}%` : '';

            this.set_applet_label(connected ?
                `${device.slice(5)} ↓ ${formatRate(read)}  ↑ ${formatRate(write)}${wear}` :
                `${device || 'SSD'} disconnected`);
            this.set_applet_icon_symbolic_name(!connected || health.smart_passed === false ?
                'dialog-warning-symbolic' : 'drive-harddisk-symbolic');
            this.set_applet_tooltip(`SSD Monitor · ${device || 'no drive'} · ${connected ? 'connected' : 'disconnected'} · snapshot ${fresh ? 'current' : 'stale or missing'}`);
            this._setRow('drive', `${record?.identity?.model || devices.find(item => item.path === device)?.model || 'Drive'} (${device || 'none'})`);
            this._setRow('smart', `SMART: ${health.smart_passed === true ? 'passed' : health.smart_passed === false ? 'warning' : 'unknown'}`);
            this._setRow('lifetime', `Lifetime remaining: ${valueOrDash(lifetime, '%')}`);
            this._setRow('temperature', `Temperature: ${valueOrDash(temperature, '°C')}`);
            this._setRow('read', `Read: ${formatRate(read)}`);
            this._setRow('write', `Write: ${formatRate(write)}`);
            this._setRow('reallocated', `Reallocated NAND blocks: ${valueOrDash(errors.reallocated_nand_blocks)}`);
            this._setRow('uncorrectable', `Uncorrectable errors: ${valueOrDash(errors.reported_uncorrectable_errors)}`);
            this._setRow('crc', `Interface CRC errors: ${valueOrDash(errors.interface_crc_errors)}`);
            this._setRow('recorded', `Recorded: ${timestamp ? new Date(timestamp).toLocaleString() : 'No snapshot yet'}`);
        } catch (error) {
            global.logError(error);
            this.set_applet_label('SSD unavailable');
        }
    }

    on_applet_clicked() {
        this._update();
        this._updateDeviceMenu(this._physicalDevices());
        this.menu.toggle();
    }

    on_applet_removed_from_panel() {
        if (this._timer) Mainloop.source_remove(this._timer);
    }
}

function main(metadata, orientation, panelHeight, instanceId) {
    return new SSDMonitorApplet(metadata, orientation, panelHeight, instanceId);
}
