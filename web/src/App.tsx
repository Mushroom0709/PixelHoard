import { Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Health from "./pages/Health";
import MyShares from "./pages/MyShares";
import ShareDetail from "./pages/ShareDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="/health" element={<Health />} />
      <Route path="/shares" element={<MyShares />} />
      <Route path="/s/:slug" element={<ShareDetail />} />
    </Routes>
  );
}