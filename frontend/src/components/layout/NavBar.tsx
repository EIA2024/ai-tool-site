import { Link } from "react-router-dom";

export default function NavBar() {
  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        AI Tool Site
      </Link>
      <div className="nav-links">
        <Link to="/tools/blank_tool">Blank Tool</Link>
        <Link to="/tools/chat_tool">Chat Tool</Link>
        <Link to="/tools/code_agent_flow_viz">Flow Visualizer</Link>
        <Link to="/tools/task_decomposer">Task Decomposer</Link>
        <Link to="/usage">Usage</Link>
      </div>
    </nav>
  );
}
