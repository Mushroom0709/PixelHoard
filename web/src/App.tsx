import { Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import Health from "./pages/Health";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="/health" element={<Health />} />
    </Routes>
  );
}