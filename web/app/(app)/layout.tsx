import { ClosetProvider } from "@/components/ClosetProvider";
import { Shell } from "@/components/Shell";
import { ToastProvider } from "@/components/Toast";
import { WorkerStatusProvider } from "@/components/WorkerStatus";

// Signed-in app chrome. The proxy guarantees a session before any of these routes render;
// data loads in the browser through Supabase with RLS.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <WorkerStatusProvider>
      <ToastProvider>
        <ClosetProvider>
          <Shell>{children}</Shell>
        </ClosetProvider>
      </ToastProvider>
    </WorkerStatusProvider>
  );
}
