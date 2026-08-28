import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { Workbench } from "./pages/Workbench";
import { Spaces } from "./pages/Spaces";
import { SpaceCreate } from "./pages/SpaceCreate";
import { SpaceDetail } from "./pages/SpaceDetail";
import { MeetingArchive } from "./pages/MeetingArchive";
import { ConfirmPage } from "./pages/ConfirmPage";
import { Entities } from "./pages/Entities";
import { SearchPage } from "./pages/SearchPage";
import { TopicPage } from "./pages/TopicPage";
import { Reports } from "./pages/Reports";
import { ReportDetail } from "./pages/ReportDetail";
import { AskEntry } from "./pages/AskEntry";
import { AskSession } from "./pages/AskSession";
import { ImportPage } from "./pages/ImportPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Workbench />} />
        <Route path="/spaces" element={<Spaces />} />
        <Route path="/spaces/new" element={<SpaceCreate />} />
        <Route path="/spaces/:id" element={<SpaceDetail />} />
        <Route path="/meetings/:id" element={<MeetingArchive />} />
        <Route path="/meetings/:id/confirm" element={<ConfirmPage />} />
        <Route path="/entities" element={<Entities />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/topics/:id" element={<TopicPage />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/reports/:id" element={<ReportDetail />} />
        <Route path="/ask" element={<AskEntry />} />
        <Route path="/ask/:sessionId" element={<AskSession />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
