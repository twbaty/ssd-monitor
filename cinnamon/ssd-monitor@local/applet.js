const Applet = imports.ui.applet;
const PopupMenu = imports.ui.popupMenu;
const Mainloop = imports.mainloop;
const GLib = imports.gi.GLib;
const ByteArray = imports.byteArray;

const HISTORY_DIR = GLib.build_filenamev([
    GLib.get_home_dir(), '.local', 'share', 'ssd-monitor'
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
        this._rows = {};
        for (const key of ['drive', 'smart', 'lifetime', 'temperature', 'read', 'write',
                           'reallocated', 'uncorrectable', 'crc', 'recorded']) {
            const item = new PopupMenu.PopupMenuItem('');
            this.menu.addMenuItem(item);
            this._rows[key] = item;
        }
        this._previous = null;
        this._update();
        this._timer = Mainloop.timeout_add_seconds(2, () => {
            this._update();
            return true;
        });
    }

    _latestRecord() {
        let dir;
        try {
            dir = GLib.Dir.open(HISTORY_DIR, 0);
        } catch (error) {
            return null;
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
                if (Array.isArray(records) && records.length > 0) {
                    return records.find(record => record.device?.path === '/dev/sda') || records[0];
                }
            } catch (error) {
                // Ignore a partial or unrelated file and try the previous snapshot.
            }
        }
        return null;
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
            const record = this._latestRecord();
            const device = record?.device?.path || '/dev/sda';
            const [read, write] = this._diskRates(device);
            const health = record?.health || {};
            const errors = record?.errors || {};
            const temperature = record?.temperature?.celsius;
            const lifetime = health.lifetime_remaining_percent;
            const timestamp = record?.collection?.timestamp_utc;
            const age = timestamp ? Date.now() - Date.parse(timestamp) : Infinity;
            const fresh = age >= 0 && age < 24 * 60 * 60 * 1000;
            const wear = fresh && lifetime !== null && lifetime !== undefined ? ` · ${lifetime}%` : '';

            this.set_applet_label(`↓ ${formatRate(read)}  ↑ ${formatRate(write)}${wear}`);
            this.set_applet_icon_symbolic_name(health.smart_passed === false ?
                'dialog-warning-symbolic' : 'drive-harddisk-symbolic');
            this.set_applet_tooltip(`SSD Monitor · ${device} · snapshot ${fresh ? 'current' : 'stale or missing'}`);
            this._setRow('drive', `${record?.identity?.model || 'Drive'} (${device})`);
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
        this.menu.toggle();
    }

    on_applet_removed_from_panel() {
        if (this._timer) Mainloop.source_remove(this._timer);
    }
}

function main(metadata, orientation, panelHeight, instanceId) {
    return new SSDMonitorApplet(metadata, orientation, panelHeight, instanceId);
}
