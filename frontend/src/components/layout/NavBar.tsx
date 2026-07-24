import { Link } from "react-router-dom";

export default function NavBar() {
  return (
    <nav className="navbar">
      <Link to="/" className="nav-brand">
        AI Tool Site
      </Link>
      <div className="nav-links">
        <Link to="/tools/blank-tool">Blank Tool</Link>
        <Link to="/tools/chat-tool">Chat Tool</Link>
      </div>
    </nav>
  );
}
