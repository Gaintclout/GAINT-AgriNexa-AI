
import { useCallback, useEffect, useState } from "react";
import { listQueuedEvidence } from "./fieldVerificationSync";

export default function FieldVerificationQueue({ userId }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const items = await listQueuedEvidence(userId);
      setRecords(items);
      setMessage("");
    } catch (error) {
      setMessage(error.message || "Unable to load offline records");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const pending = records.filter(
    item => item.sync_status === "pending"
  ).length;

  const synced = records.filter(
    item => item.sync_status === "synced"
  ).length;

  const failed = records.filter(
    item => item.sync_status === "pending" &&
      item.attempts > 0
  ).length;

  return (
    <section
      aria-label="Field verification offline queue"
      style={{
        background: "#fff",
        border: "1px solid #e2e8f0",
        borderRadius: 16,
        padding: 20,
        marginTop: 20
      }}
    >
      <h3 style={{ marginTop: 0 }}>
        Field Verification — Offline Queue
      </h3>

      <p style={{ color: "#64748b" }}>
        View locally queued evidence. Live synchronization
        is not enabled yet.
      </p>

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
        gap: 12,
        marginBottom: 16
      }}>
        {[
          ["Pending", pending],
          ["Synced", synced],
          ["Failed Attempts", failed]
        ].map(([label, value]) => (
          <div
            key={label}
            style={{
              padding: 14,
              background: "#f1f5f9",
              borderRadius: 12
            }}
          >
            <div style={{
              fontSize: 25,
              fontWeight: 700,
              color: "#0f172a"
            }}>
              {value}
            </div>
            <div style={{ color: "#475569" }}>
              {label}
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={refresh}
        disabled={loading}
        style={{
          padding: "10px 18px",
          borderRadius: 10,
          border: "1px solid #cbd5e1",
          background: "#fff",
          cursor: loading ? "wait" : "pointer"
        }}
      >
        {loading ? "Refreshing..." : "Refresh Queue"}
      </button>

      {message && (
        <p role="alert" style={{ color: "#b91c1c" }}>
          {message}
        </p>
      )}

      {records.length === 0 ? (
        <p style={{ color: "#64748b", marginTop: 16 }}>
          No queued evidence records found.
        </p>
      ) : (
        <div style={{ overflowX: "auto", marginTop: 16 }}>
          <table style={{
            width: "100%",
            borderCollapse: "collapse",
            textAlign: "left"
          }}>
            <thead>
              <tr>
                {["Record", "Parcel", "Status", "Attempts"].map(
                  heading => (
                    <th
                      key={heading}
                      style={{ padding: 10, borderBottom: "1px solid #ddd" }}
                    >
                      {heading}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {records.map(item => (
                <tr key={item.client_record_id}>
                  <td style={{ padding: 10 }}>
                    {item.client_record_id}
                  </td>
                  <td style={{ padding: 10 }}>
                    {item.parcel_id}
                  </td>
                  <td style={{ padding: 10 }}>
                    {item.sync_status}
                  </td>
                  <td style={{ padding: 10 }}>
                    {item.attempts || 0}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
