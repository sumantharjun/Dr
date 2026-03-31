import { useEffect, useState } from "react";
import { Cpu, Plus, Trash2, Wifi, WifiOff } from "lucide-react";
import api from "../services/api";
import { Device } from "../types";
import { formatDistanceToNow } from "date-fns";

type PairingStep = "idle" | "step1" | "step2" | "step3" | "done";

export default function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [pairing, setPairing] = useState<PairingStep>("idle");
  const [form, setForm] = useState({ device_name: "", mac_address: "", wifi_ssid: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchDevices();
  }, []);

  async function fetchDevices() {
    const { data } = await api.get("/devices/");
    setDevices(data);
  }

  async function handlePair() {
    setError("");
    setLoading(true);
    try {
      await api.post("/devices/", {
        device_name: form.device_name,
        mac_address: form.mac_address,
        wifi_ssid: form.wifi_ssid || undefined,
      });
      await fetchDevices();
      setPairing("done");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Pairing failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(id: number) {
    if (!confirm("Remove this device?")) return;
    await api.delete(`/devices/${id}`);
    setDevices((prev) => prev.filter((d) => d.id !== id));
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Devices</h1>
          <p className="text-gray-500 text-sm mt-1">Manage your paired smart feeding devices</p>
        </div>
        <button
          onClick={() => { setPairing("step1"); setError(""); }}
          className="flex items-center gap-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
        >
          <Plus className="w-4 h-4" />
          Pair Device
        </button>
      </div>

      {/* Pairing Wizard */}
      {pairing !== "idle" && pairing !== "done" && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Pair New Device — Wi-Fi Provisioning</h2>

          {/* Steps indicator */}
          <div className="flex items-center gap-2 mb-6">
            {["Connect to Device AP", "Enter Credentials", "Confirm"].map((s, i) => (
              <div key={i} className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-full text-xs font-semibold flex items-center justify-center
                  ${Number(pairing.replace("step", "")) > i ? "bg-primary-600 text-white" : "bg-gray-100 text-gray-500"}`}>
                  {i + 1}
                </div>
                <span className="text-xs text-gray-500 hidden sm:block">{s}</span>
                {i < 2 && <div className="w-8 h-px bg-gray-200" />}
              </div>
            ))}
          </div>

          {pairing === "step1" && (
            <div>
              <p className="text-sm text-gray-700 mb-4">
                1. On the device, hold the pairing button for 3 seconds until the LED blinks blue.<br />
                2. On your phone/computer, connect to the Wi-Fi network named <strong>BabyFeeder-XXXX</strong>.<br />
                3. Once connected, come back here and click Next.
              </p>
              <div className="flex gap-3">
                <button onClick={() => setPairing("idle")} className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">Cancel</button>
                <button onClick={() => setPairing("step2")} className="px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700">
                  I'm connected — Next
                </button>
              </div>
            </div>
          )}

          {pairing === "step2" && (
            <div className="space-y-4">
              <p className="text-sm text-gray-600">Enter your device details and home Wi-Fi network.</p>
              {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg">{error}</div>}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Device Name</label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                  placeholder="e.g. Nursery Feeder"
                  value={form.device_name}
                  onChange={(e) => setForm({ ...form, device_name: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Device MAC Address</label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                  placeholder="AA:BB:CC:DD:EE:FF"
                  value={form.mac_address}
                  onChange={(e) => setForm({ ...form, mac_address: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Home Wi-Fi SSID</label>
                <input
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:outline-none"
                  placeholder="Your network name"
                  value={form.wifi_ssid}
                  onChange={(e) => setForm({ ...form, wifi_ssid: e.target.value })}
                />
              </div>
              <div className="flex gap-3">
                <button onClick={() => setPairing("step1")} className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">Back</button>
                <button
                  onClick={() => setPairing("step3")}
                  disabled={!form.device_name || !form.mac_address}
                  className="px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}

          {pairing === "step3" && (
            <div>
              <p className="text-sm text-gray-700 mb-4">
                Confirm and register your device to your account.
              </p>
              <div className="bg-gray-50 rounded-lg p-4 text-sm space-y-2 mb-4">
                <div className="flex justify-between"><span className="text-gray-500">Name</span><span className="font-medium">{form.device_name}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">MAC</span><span className="font-medium font-mono">{form.mac_address}</span></div>
                {form.wifi_ssid && <div className="flex justify-between"><span className="text-gray-500">Wi-Fi</span><span className="font-medium">{form.wifi_ssid}</span></div>}
              </div>
              {error && <div className="bg-red-50 text-red-700 text-sm px-4 py-3 rounded-lg mb-4">{error}</div>}
              <div className="flex gap-3">
                <button onClick={() => setPairing("step2")} className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50">Back</button>
                <button
                  onClick={handlePair}
                  disabled={loading}
                  className="px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
                >
                  {loading ? "Pairing..." : "Register Device"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {pairing === "done" && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6 flex items-center justify-between">
          <p className="text-green-700 text-sm font-medium">Device paired successfully!</p>
          <button onClick={() => setPairing("idle")} className="text-green-600 text-sm underline">Dismiss</button>
        </div>
      )}

      {/* Device List */}
      {devices.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <Cpu className="w-12 h-12 mx-auto text-gray-300 mb-3" />
          <p className="text-gray-500">No devices paired yet. Click "Pair Device" to get started.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {devices.map((d) => (
            <div key={d.id} className="bg-white rounded-xl border border-gray-200 p-5 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-primary-50 rounded-xl flex items-center justify-center">
                  {d.status === "online" ? (
                    <Wifi className="w-5 h-5 text-primary-600" />
                  ) : (
                    <WifiOff className="w-5 h-5 text-gray-400" />
                  )}
                </div>
                <div>
                  <p className="font-semibold text-gray-900">{d.device_name}</p>
                  <p className="text-xs text-gray-400 font-mono">{d.mac_address}</p>
                  {d.last_seen && (
                    <p className="text-xs text-gray-400">
                      Last seen {formatDistanceToNow(new Date(d.last_seen), { addSuffix: true })}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3">
                <StatusBadge status={d.status} />
                <button
                  onClick={() => handleDelete(d.id)}
                  className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: Device["status"] }) {
  const map: Record<string, string> = {
    online: "bg-green-100 text-green-700",
    offline: "bg-gray-100 text-gray-500",
    pairing: "bg-yellow-100 text-yellow-700",
    error: "bg-red-100 text-red-700",
  };
  return (
    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${map[status] || map.offline}`}>
      {status}
    </span>
  );
}
