import { Routes, Route } from "react-router-dom";
import Layout from "./components/layout/Layout";
import ToolList from "./pages/ToolList";
import ToolPage from "./pages/ToolPage";
import UsagePage from "./pages/UsagePage";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<ToolList />} />
        <Route path="/usage" element={<UsagePage />} />
      </Route>
      {/* Single dynamic route: layout (standard vs fullscreen) is resolved per
          tool from its manifest inside ToolPage. */}
      <Route path="/tools/:toolId" element={<ToolPage />} />
    </Routes>
  );
}

export default App;
