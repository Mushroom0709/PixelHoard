import { Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Health from "./pages/Health";
import Login from "./pages/Login";
import Register from "./pages/Register";
import MyShares from "./pages/MyShares";
import ShareDetail from "./pages/ShareDetail";
import { AuthProvider } from "./auth";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Index />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/health" element={<Health />} />
        <Route path="/shares" element={<MyShares />} />
        <Route path="/s/:slug" element={<ShareDetail />} />
        {/* 游客分享链接:/s/{slug}/{tokenCode} */}
        <Route path="/s/:slug/:tokenCode" element={<ShareDetail />} />
      </Routes>
    </AuthProvider>
  );
}