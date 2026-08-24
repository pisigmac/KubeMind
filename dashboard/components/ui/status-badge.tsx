export function StatusBadge({ healthy }: { healthy: boolean }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${
      healthy ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
    }`}>
      {healthy ? "Healthy" : "Down"}
    </span>
  );
}
