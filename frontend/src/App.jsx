import { useEffect, useState } from 'react';
import {
  Routes,
  Route,
  NavLink,
  Navigate,
  useNavigate,
  useParams,
} from 'react-router-dom';

import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  FolderOpen,
  LayoutDashboard,
  LifeBuoy,
  Menu,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldAlert,
  Ticket as TicketIcon,
  Trash2,
  UploadCloud,
  X,
  Zap,
  Pencil,
  Save,
  XCircle,
  History,
  TrendingUp,
  Gauge,
  Users,
  CalendarDays,
  CircleCheck,
  CircleAlert,
  Timer,
  LogOut
} from 'lucide-react';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

import api, {
  getTicket,
  getTicketHistory,
  getActionHistory,
  approveResponse,
  rejectResponse,
  editResponse,
} from './services/api';
import Login from './pages/Login';
import { useAuth } from './context/AuthContext';

// --------------------------------------------------
// NAVIGATION
// --------------------------------------------------


const nav = [
  ['Overview', '/', LayoutDashboard, ['Admin', 'Agent', 'Viewer']],
  ['All tickets', '/tickets', TicketIcon, ['Admin', 'Agent', 'Viewer']],
  ['Knowledge base', '/knowledge', BookOpen, ['Admin', 'Agent', 'Viewer']],
  ['Escalations', '/escalations', ShieldAlert, ['Admin', 'Agent']],
  ['System health', '/settings', Settings, ['Admin']],
];


const statuses = [
  'Open',
  'In Progress',
  'Pending',
  'Escalated',
  'Resolved',
];

const chartColors = ['#E66A6A', '#E8A23D', '#6478E8', '#21A67A'];

// --------------------------------------------------
// APPLICATION SHELL
// --------------------------------------------------


function Shell({ children }) {
  const [mobile, setMobile] = useState(false);

  const { user, logout } = useAuth();

  const visibleNav = nav.filter(([label, path, Icon, roles]) =>
    roles.includes(user?.role)
  ); 

  const initials = user?.full_name
    ? user.full_name
        .split(' ')
        .map((part) => part[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : 'U';

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobile ? 'show' : ''}`}>
        <div className="brand">
          <div className="brand-mark">
            <Zap size={19} />
          </div>

          <div>
            <b>
              resolve<span>ai</span>
            </b>
            <small>SUPPORT INTELLIGENCE</small>
          </div>

          <button
            className="mobile-close"
            onClick={() => setMobile(false)}
          >
            <X />
          </button>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <nav>
          {visibleNav.map(([label, path, Icon]) => (
            <NavLink
              onClick={() => setMobile(false)}
              key={path}
              to={path}
              className={({ isActive }) =>
                'nav-link ' + (isActive ? 'active' : '')
              }
            >
              <Icon size={18} />
              <span>{label}</span>

              {label === 'Escalations' && (
                <i className="nav-dot" />
              )}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="status-pill">
            <span />
            AI engine ready
          </div>

          <div className="profile">
            <div className="avatar">{initials}</div>

            <div className="profile-info">
              <b>{user?.full_name || 'User'}</b>
              <small>{user?.role || 'Unknown role'}</small>
            </div>

            <button
              className="icon-btn logout-btn"
              onClick={handleLogout}
              title="Logout"
              aria-label="Logout"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>

      {mobile && (
        <div
          className="scrim"
          onClick={() => setMobile(false)}
        />
      )}

      <main className="main">
        <header className="topbar">
          <button
            className="mobile-menu"
            onClick={() => setMobile(true)}
          >
            <Menu />
          </button>

          <div className="crumb">
            Workspace <ChevronRight size={14} />
            <b>Support operations</b>
          </div>

          <div className="top-actions">
            <span className="live">
              <i /> System operational
            </span>

            <div className="avatar small-avatar">
              {initials}
            </div>
          </div>
        </header>

        <div className="content">{children}</div>
      </main>
    </div>
  );
}


// --------------------------------------------------
// REUSABLE COMPONENTS
// --------------------------------------------------

function PageHead({ eyebrow, title, desc, action }) {
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{desc}</p>
      </div>

      {action}
    </div>
  );
}

function Metric({ label, value, sub, Icon, tone }) {
  return (
    <div className="metric card">
      <div className="metric-top">
        <span>{label}</span>

        <div className={`metric-icon ${tone}`}>
          <Icon size={18} />
        </div>
      </div>

      <strong>{value ?? 'â€”'}</strong>
      <small>{sub}</small>
    </div>
  );
}

function Empty({ text }) {
  return (
    <div className="empty">
      <FolderOpen size={25} />
      <span>{text}</span>
    </div>
  );
}

function Badge({ children, tone }) {
  const defaultTone = String(children)
    .toLowerCase()
    .replaceAll(' ', '-');

  return (
    <span className={`badge ${tone || defaultTone}`}>
      {children}
    </span>
  );
}

function Field({ label, children, wide }) {
  return (
    <label className={wide ? 'field wide' : 'field'}>
      <span>{label}</span>
      {children}
    </label>
  );
}

// --------------------------------------------------
// TICKET TABLE
// --------------------------------------------------

function TicketTable({ tickets }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>TICKET</th>
            <th>CUSTOMER</th>
            <th>SUBJECT</th>
            <th>PRIORITY</th>
            <th>STATUS</th>
            <th>CREATED</th>
          </tr>
        </thead>

        <tbody>
          {tickets.length ? (
            tickets.map((t) => (
              <tr key={t.ticket_id}>
                <td>
                  <NavLink
                    className="ticket-id"
                    to={`/tickets/${t.ticket_id}`}
                  >
                    {t.ticket_id}
                  </NavLink>
                </td>

                <td>
                  <b>{t.customer_name || 'Restricted'}</b>
                  <small>{t.customer_email || 'Customer details hidden'}</small>
                </td>

                <td className="subject-cell">{t.subject}</td>

                <td>
                  <Badge>{t.priority}</Badge>
                </td>

                <td>
                  <Badge>{t.status}</Badge>
                </td>

                <td>
                  {new Date(t.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan="6">
                <Empty text="No tickets found" />
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// --------------------------------------------------
// DASHBOARD
// --------------------------------------------------

function Dashboard() {
  const [data, setData] = useState(null);
  const [cats, setCats] = useState([]);
  const [priorities, setPriorities] = useState([]);
  const [trends, setTrends] = useState([]);
  const [sla, setSla] = useState(null);
  const [approvals, setApprovals] = useState(null);
  const [activity, setActivity] = useState(null);
  const [days, setDays] = useState(7);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [overviewRes, categoriesRes, prioritiesRes, trendsRes,
        slaRes, approvalsRes, activityRes] = await Promise.all([
        api.get('/api/analytics/overview'),
        api.get('/api/analytics/categories'),
        api.get('/api/analytics/priorities'),
        api.get('/api/analytics/trends', { params: { days } }),
        api.get('/api/analytics/sla'),
        api.get('/api/analytics/approvals'),
        api.get('/api/analytics/support-activity'),
      ]);

      setData(overviewRes.data);
      setCats(Array.isArray(categoriesRes.data) ? categoriesRes.data : []);
      setPriorities(Array.isArray(prioritiesRes.data) ? prioritiesRes.data : []);
      setTrends(Array.isArray(trendsRes.data) ? trendsRes.data : (trendsRes.data?.items || []));
      setSla(slaRes.data);
      setApprovals(approvalsRes.data);
      setActivity(activityRes.data);
      setErr('');
    } catch (error) {
      console.error('Analytics loading failed:', error);
      setErr(
        error.response?.data?.detail ||
        'Analytics could not be loaded. Check the FastAPI server and try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [days]);

  const approvalDistribution = (() => {
    const raw = approvals?.status_distribution;
    if (Array.isArray(raw)) return raw;
    if (raw && typeof raw === 'object') {
      return Object.entries(raw).map(([name, value]) => ({ name, value }));
    }
    return [];
  })();

  const actionDistribution = (() => {
    const raw = activity?.actions_by_actor;
    if (Array.isArray(raw)) {
      // Supports either pre-aggregated actor rows or actor/action/count rows.
      const grouped = {};
      raw.forEach((item) => {
        const actor = item.actor || item.name || 'Support team';
        if (!grouped[actor]) grouped[actor] = { name: actor, Approved: 0, Edited: 0, Rejected: 0 };
        if (item.action) {
          const action = String(item.action).toUpperCase();
          const key = action === 'APPROVED' ? 'Approved' : action === 'EDITED' ? 'Edited': action === 'REJECTED' ? 'Rejected' : null;
          if (key) grouped[actor][key] += Number(item.count ?? item.value ?? 1);
        } else {
          grouped[actor].Approved += Number(item.APPROVED ?? item.approved ?? 0);
          grouped[actor].Edited += Number(item.EDITED ?? item.edited ?? 0);
          grouped[actor].Rejected += Number(item.REJECTED ?? item.rejected ?? 0);
        }
      });
      return Object.values(grouped);
    }
    if (raw && typeof raw === 'object') {
      return Object.entries(raw).map(([name, actions]) => ({
        name,
        Approved: actions?.APPROVED ?? actions?.approved ?? 0,
        Edited: actions?.EDITED ?? actions?.edited ?? 0,
        Rejected: actions?.REJECTED ?? actions?.rejected ?? 0,
      }));
    }
    return [];
  })();

  const slaPercent = Number(sla?.compliance_percentage ?? 0);
  const number = (value) => value == null ? 'â€”' : value;
  const formatDate = (value) => {
    if (!value) return '';
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? String(value)
      : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
  };

  return (
    <>
      <PageHead
        eyebrow="SUPPORT INTELLIGENCE / OVERVIEW"
        title="Support operations"
        desc="A live view of ticket volume, resolution workflow and service-level performance."
        action={
          <button className="btn secondary" onClick={load} disabled={loading}>
            <RefreshCw size={15} className={loading ? 'spin' : ''} />
            {loading ? 'Refreshing...' : 'Refresh data'}
          </button>
        }
      />

      {err && (
        <div className="alert">
          <AlertCircle size={17} />
          {err}
        </div>
      )}

      <div className="dashboard-intro">
        <div>
          <span className="intro-kicker"><span className="pulse-dot" /> LIVE WORKSPACE</span>
          <h2>Operational snapshot</h2>
          <p>Key support metrics aggregated from your ticket database.</p>
        </div>
        <div className="range-control">
          <CalendarDays size={15} />
          <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
      </div>

      <div className="metrics-grid">
        <Metric label="Total tickets" value={number(data?.total_tickets)}
          sub="All-time ticket volume" Icon={TicketIcon} tone="blue" />
        <Metric label="Open tickets" value={number(data?.open_tickets)}
          sub="Awaiting resolution" Icon={Clock3} tone="amber" />
        <Metric label="Resolved tickets" value={number(data?.resolved_tickets)}
          sub="Marked resolved" Icon={CheckCircle2} tone="green" />
        <Metric label="Escalated tickets" value={number(data?.escalated_tickets)}
          sub="Require human attention" Icon={ShieldAlert} tone="red" />
      </div>

      <div className="metrics-grid second">
        <Metric label="Critical priority" value={number(data?.critical_tickets)}
          sub="Highest urgency" Icon={AlertCircle} tone="red" />
        <Metric label="Avg. resolution time"
          value={data?.average_resolution_hours == null ? 'â€”' : `${data.average_resolution_hours}h`}
          sub="Resolved tickets only" Icon={Activity} tone="violet" />
        <Metric label="AI processed" value={number(data?.ai_handled)}
          sub="AI result without escalation" Icon={Zap} tone="blue" />
        <Metric label="Human escalations" value={number(data?.human_escalated)}
          sub="Flagged for agent review" Icon={LifeBuoy} tone="amber" />
      </div>

      <div className="analytics-grid trends-row">
        <section className="card analytics-card trend-card">
          <div className="section-head">
            <div>
              <span className="card-kicker">TICKET FLOW</span>
              <h3>Ticket trends</h3>
              <p>Created and resolved tickets over the selected period.</p>
            </div>
            <span className="tag">LAST {days} DAYS</span>
          </div>
          <div className="chart-wrap trend-chart">
            {trends.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trends} barGap={5}>
                  <XAxis dataKey="date" tickFormatter={formatDate}
                    tick={{ fill: '#8290a8', fontSize: 10 }} axisLine={false}
                    tickLine={false} minTickGap={24} />
                  <YAxis allowDecimals={false} tick={{ fill: '#8290a8', fontSize: 10 }}
                    axisLine={false} tickLine={false} width={28} />
                  <Tooltip
                    contentStyle={{ background: '#111c31', border: '1px solid #293a59',
                      borderRadius: 10, color: '#e8eefb', fontSize: 11 }}
                    labelFormatter={formatDate}
                  />
                  <Bar dataKey="created" name="Created" fill="#7185ff"
                    radius={[5, 5, 0, 0]} maxBarSize={18} />
                  <Bar dataKey="resolved" name="Resolved" fill="#35c99a"
                    radius={[5, 5, 0, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Empty text={loading ? 'Loading ticket trends...' : 'No trend data available'} />}
          </div>
          <div className="chart-legend">
            <span><i className="legend-blue" /> Created</span>
            <span><i className="legend-green" /> Resolved</span>
          </div>
        </section>

        <section className="card analytics-card">
          <div className="section-head">
            <div>
              <span className="card-kicker">CLASSIFICATION</span>
              <h3>Priority distribution</h3>
              <p>Current ticket priority mix.</p>
            </div>
            <span className="tag">ALL TICKETS</span>
          </div>
          <div className="chart-wrap">
            {priorities.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={priorities} dataKey="value" nameKey="name"
                    innerRadius={57} outerRadius={83} paddingAngle={4}
                    stroke="none">
                    {priorities.map((item, index) => (
                      <Cell key={item.name} fill={chartColors[index % chartColors.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#111c31', border: '1px solid #293a59',
                      borderRadius: 10, color: '#e8eefb', fontSize: 11 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : <Empty text="No priority data available" />}
          </div>
          <div className="legend">
            {priorities.map((item, index) => (
              <span key={item.name}>
                <i style={{ background: chartColors[index % chartColors.length] }} />
                {item.name} <b>{item.value}</b>
              </span>
            ))}
          </div>
        </section>
      </div>

      <div className="analytics-grid">
        <section className="card analytics-card">
          <div className="section-head">
            <div>
              <span className="card-kicker">KNOWLEDGE SIGNALS</span>
              <h3>Ticket categories</h3>
              <p>Issue classification across support requests.</p>
            </div>
            <span className="tag">DATABASE</span>
          </div>
          <div className="chart-wrap category-chart">
            {cats.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cats} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <XAxis type="number" allowDecimals={false} hide />
                  <YAxis type="category" dataKey="name" width={112}
                    tick={{ fill: '#aab6ca', fontSize: 10 }} axisLine={false}
                    tickLine={false} />
                  <Tooltip
                    contentStyle={{ background: '#111c31', border: '1px solid #293a59',
                      borderRadius: 10, color: '#e8eefb', fontSize: 11 }}
                  />
                  <Bar dataKey="value" name="Tickets" fill="#8b78ff"
                    radius={[0, 5, 5, 0]} maxBarSize={18} />
                </BarChart>
              </ResponsiveContainer>
            ) : <Empty text="No category data available" />}
          </div>
        </section>

        <section className="card analytics-card sla-card">
          <div className="section-head">
            <div>
              <span className="card-kicker">SERVICE LEVEL</span>
              <h3>SLA compliance</h3>
              <p>Evaluated against configured priority targets.</p>
            </div>
            <Gauge size={19} className="section-icon" />
          </div>
          <div className="sla-score">
            <strong>{sla?.compliance_percentage == null ? 'â€”' : `${slaPercent.toFixed(1)}%`}</strong>
            <span>compliance rate</span>
          </div>
          <div className="sla-track">
            <span style={{ width: `${Math.max(0, Math.min(100, slaPercent))}%` }} />
          </div>
          <div className="sla-stats">
            <div><i className="dot-green" /><span>Within SLA</span><b>{number(sla?.within_sla)}</b></div>
            <div><i className="dot-red" /><span>Breached</span><b>{number(sla?.breached)}</b></div>
            <div><i className="dot-muted" /><span>Unknown</span><b>{number(sla?.unknown)}</b></div>
          </div>
          <p className="footnote">Elapsed calendar hours; business-hour pauses are not applied.</p>
        </section>
      </div>

      <div className="analytics-grid">
        <section className="card analytics-card">
          <div className="section-head">
            <div>
              <span className="card-kicker">HUMAN-IN-THE-LOOP</span>
              <h3>AI response approvals</h3>
              <p>Current response states and review outcomes.</p>
            </div>
            <CircleCheck size={19} className="section-icon" />
          </div>
          <div className="approval-kpis">
            <div><strong>{number(approvals?.approval_rate)}{approvals?.approval_rate == null ? '' : '%'}</strong><span>Approval rate</span></div>
            <div><strong>{number(approvals?.rejection_rate)}{approvals?.rejection_rate ==null ? '' : '%'}</strong><span>Rejection rate</span></div>
            <div><strong>{number(approvals?.total_responses)}</strong><span>AI responses</span></div>
          </div>
          <div className="distribution-list">
            {approvalDistribution.length ? approvalDistribution.map((item) => (
              <div className="distribution-row" key={item.name}>
                <span>{item.name}</span>
                <div className="distribution-track"><i
                  className={`distribution-fill ${String(item.name).toLowerCase()}`}
                  style={{ width: `${approvals?.total_responses
                    ? Math.min(100, (Number(item.value) / approvals.total_responses) * 100)
                    : 0}%` }}
                /></div>
                <b>{item.value}</b>
              </div>
            )) : (
              <div className="muted">No approval distribution available.</div>
            )}
          </div>
          <div className="audit-total">
            <History size={14} />
            <span>{number(approvals?.total_actions)} recorded review actions</span>
          </div>
        </section>

        <section className="card analytics-card">
          <div className="section-head">
            <div>
              <span className="card-kicker">TEAM WORKFLOW</span>
              <h3>Support activity</h3>
              <p>Recorded agent actions and internal notes.</p>
            </div>
            <Users size={19} className="section-icon" />
          </div>
          <div className="activity-kpis">
            <div><strong>{number(activity?.total_support_actions)}</strong><span>Review actions</span></div>
            <div><strong>{number(activity?.total_internal_notes)}</strong><span>Internal notes</span></div>
          </div>
          {actionDistribution.length ? (
            <div className="activity-list">
              {actionDistribution.map((item) => (
                <div className="activity-row" key={item.name}>
                  <div className="activity-avatar">{String(item.name).slice(0, 1).toUpperCase()}</div>
                  <div className="activity-person">
                    <b>{item.name}</b>
                    <small>{item.Approved} approved Â· {item.Edited} edited Â· {item.Rejected} rejected</small>
                  </div>
                  <span className="activity-count">{item.Approved + item.Edited + item.Rejected}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="activity-empty"><Users size={22} /><span>No support activity recorded yet.</span></div>
          )}
          {activity?.individual_agent_performance_available === false && (
            <p className="footnote">Individual performance attribution requires authenticated agent identities.</p>
          )}
        </section>
      </div>

      <section className="card table-card recent-card">
        <div className="section-head">
          <div>
            <span className="card-kicker">LATEST INBOUND</span>
            <h3>Recent tickets</h3>
            <p>Latest customer conversations from the ticket queue.</p>
          </div>
          <NavLink to="/tickets" className="text-link">
            View all tickets <ArrowUpRight size={15} />
          </NavLink>
        </div>
        <TicketTable tickets={data?.recent_tickets || []} />
      </section>
    </>
  );
}

// --------------------------------------------------
// ALL TICKETS
// --------------------------------------------------

function Tickets() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const load = () =>
    api
      .get('/api/tickets', {
        params: {
          q,
          status: status || undefined,
        },
      })
      .then((r) => {
        setItems(r.data.items);
        setError('');
      })
      .catch(() => {
        setError('Could not load tickets. Is the backend running?');
      });

  useEffect(() => {
    load();
  }, [q, status]);

  return (
    <>
      <PageHead
        eyebrow="CUSTOMER SUPPORT"
        title="All tickets"
        desc="Search, triage and manage incoming customer requests."
        action={
  ['Admin', 'Agent'].includes(user?.role) && (
    <NavLink className="btn primary" to="/tickets/new">
      <Plus size={17} />
      Create ticket
    </NavLink>
  )
}
      />

      {error && <div className="alert">{error}</div>}

      <div className="card filterbar">
        <div className="searchbox">
          <Search size={17} />
          <input
            placeholder="Search ticket, subject or email..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </div>

        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          {statuses.map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </select>
      </div>

      <section className="card table-card">
        <TicketTable tickets={items} />
      </section>
    </>
  );
}

// --------------------------------------------------
// CREATE TICKET
// --------------------------------------------------

function CreateTicket() {
  const [form, setForm] = useState({
    customer_name: '',
    customer_email: '',
    subject: '',
    description: '',
  });

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const change = (e) => {
    setForm({
      ...form,
      [e.target.name]: e.target.value,
    });
  };

  async function submit(e) {
    e.preventDefault();

    setBusy(true);
    setError('');

    try {
      const r = await api.post('/api/tickets', form);
      navigate(`/tickets/${r.data.ticket_id}`);
    } catch (e) {
      setError(
        e.response?.data?.detail ||
          'Ticket could not be created. Check backend connection.'
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHead
        eyebrow="CUSTOMER SUPPORT"
        title="Create a ticket"
        desc="Capture the customer issue. AI analysis can be run after ticket creation."
      />

      {error && <div className="alert">{error}</div>}

      <form className="card form-card" onSubmit={submit}>
        <div className="form-grid">
          <Field label="Customer name">
            <input
              required
              name="customer_name"
              value={form.customer_name}
              onChange={change}
              placeholder="e.g. Asha Sharma"
            />
          </Field>

          <Field label="Customer email">
            <input
              required
              type="email"
              name="customer_email"
              value={form.customer_email}
              onChange={change}
              placeholder="name@company.com"
            />
          </Field>

          <Field label="Subject" wide>
            <input
              required
              minLength="4"
              name="subject"
              value={form.subject}
              onChange={change}
              placeholder="Briefly describe the issue"
            />
          </Field>

          <Field label="Issue description" wide>
            <textarea
              required
              minLength="10"
              rows="6"
              name="description"
              value={form.description}
              onChange={change}
              placeholder="What happened? Include relevant error messages and steps already tried."
            />
          </Field>
        </div>

        <div className="form-footer">
          <span className="muted">
            Ticket will be saved in the database.
          </span>

          <button
            disabled={busy}
            className="btn primary"
            type="submit"
          >
            {busy ? 'Creating...' : 'Create ticket'}
            <ChevronRight size={16} />
          </button>
        </div>
      </form>
    </>
  );
}

// --------------------------------------------------
// TICKET DETAILS + AI COPILOT + APPROVAL WORKFLOW
// --------------------------------------------------

function TicketDetail() {
  const { id } = useParams();
  const { user } = useAuth();

  const canManageTicket = ['Admin', 'Agent'].includes(user?.role);
  const [t, setT] = useState(null);
  const [history, setHistory] = useState([]);
  const [actionHistory, setActionHistory] = useState([]);

  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [err, setErr] = useState('');

  const [editMode, setEditMode] = useState(false);
  const [editedResponse, setEditedResponse] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');

  // Load ticket, status history and action audit history.
  const load = async () => {
    try {
      const [ticketResponse, historyResponse, actionResponse] =
        await Promise.all([
          getTicket(id),
          getTicketHistory(id),
          canManageTicket ? getActionHistory(id) : Promise.resolve({ data: [] }),
        ]);

      setT(ticketResponse.data);
      setHistory(historyResponse.data);
      setActionHistory(actionResponse.data);
      setErr('');
    } catch (error) {
      console.error('Ticket loading failed:', error);
      setErr(
        error.response?.data?.detail ||
          'Ticket not found or backend unavailable.'
      );
    }
  };

  useEffect(() => {
    setT(null);
    setEditMode(false);
    setEditedResponse('');
    setRejectionReason('');
    load();
  }, [id]);

  // Run AI analysis.
  async function runAI() {
    if (!canManageTicket) return;
    setBusy(true);
    setErr('');

    try {
      await api.post(`/api/ai/resolve/${id}`);
      setEditMode(false);
      await load();
    } catch (e) {
      setErr(e.response?.data?.detail || 'AI analysis failed.');
    } finally {
      setBusy(false);
    }
  }

  // Update ticket status.
  async function updateStatus(status) {
    if (!canManageTicket) return;
    setBusy(true);
    setErr('');

    try {
      await api.patch(`/api/tickets/${id}/status`, {
        status,
        note: 'Updated by support agent',
      });

      await load();
    } catch (e) {
      setErr(
        e.response?.data?.detail ||
          'Could not update ticket status.'
      );
    } finally {
      setBusy(false);
    }
  }

  // Save internal note.
  async function addNote() {
    if (!canManageTicket || !note.trim()) return;

    setBusy(true);
    setErr('');

    try {
      await api.post(`/api/agents/${id}/notes`, {
        note: note.trim(),
      });

      setNote('');
      await load();
    } catch (e) {
      setErr(e.response?.data?.detail || 'Could not save note.');
    } finally {
      setBusy(false);
    }
  }

  // Approve customer response.
  async function approve() {
    if (!canManageTicket || !canApprove) {
      setErr('This response is not eligible for approval.');
      return;
    }

    setBusy(true);
    setErr('');

    try {
      await approveResponse(id);
      await load();
    } catch (error) {
      setErr(
        error.response?.data?.detail ||
          'Could not approve the AI response.'
      );
    } finally {
      setBusy(false);
    }
  }

  // Start editing response.
  function startEditing() {
    if (!canManageTicket || !canEdit) return;
    setEditedResponse(ai.customer_response || '');
    setEditMode(true);
    setErr('');
  }

  // Save edited response.
  async function saveEditedResponse() {
    if (!canManageTicket || !canEdit) return;
    if (!editedResponse.trim()) {
      setErr('Customer response cannot be empty.');
      return;
    }

    if (editedResponse.trim().length < 5) {
      setErr('Customer response must contain at least 5 characters.');
      return;
    }

    setBusy(true);
    setErr('');

    try {
      await editResponse(id, editedResponse.trim());

      setEditMode(false);
      setEditedResponse('');

      await load();
    } catch (error) {
      setErr(
        error.response?.data?.detail ||
          'Could not update customer response.'
      );
    } finally {
      setBusy(false);
    }
  }

  // Cancel editing.
  function cancelEditing() {
    setEditMode(false);
    setEditedResponse('');
    setErr('');
  }

  // Reject customer response.
  async function reject() {
    if (!canManageTicket) return;
    const reason = rejectionReason.trim();

    if (reason.length < 5) {
      setErr('Rejection reason must contain at least 5 characters.');
      return;
    }

    if (!canReject) {
      setErr('This response cannot be rejected.');
      return;
    }

    setBusy(true);
    setErr('');

    try {
      await rejectResponse(id, reason);

      setRejectionReason('');
      await load();
    } catch (error) {
      setErr(
        error.response?.data?.detail ||
          'Could not reject the AI response.'
      );
    } finally {
      setBusy(false);
    }
  }

  if (!t) {
    return (
      <>
        <PageHead
          eyebrow="TICKET DETAILS"
          title={id}
          desc={err || 'Loading ticket...'}
        />
      </>
    );
  }

  const ai = t.ai_result;

  const canApprove =
    canManageTicket &&
    Boolean(ai) &&
    ai.available === true &&
    Boolean(ai.customer_response?.trim()) &&
    ai.escalation_required !== true &&
    ai.approval_status !== 'Approved' &&
    ai.approval_status !== 'Rejected' &&
    t.status !== 'Resolved';

  const canEdit =
    canManageTicket &&
    Boolean(ai) &&
    ai.available === true &&
    Boolean(ai.customer_response?.trim()) &&
    ai.escalation_required !== true &&
    ai.approval_status !== 'Approved' &&
    t.status !== 'Resolved';

  const canReject =
    canManageTicket &&
    Boolean(ai) &&
    ai.available === true &&
    Boolean(ai.customer_response?.trim()) &&
    ai.escalation_required !== true &&
    ai.approval_status !== 'Approved' &&
    ai.approval_status !== 'Rejected' &&
    t.status !== 'Resolved';

  return (
    <>
      <PageHead
        eyebrow="TICKET DETAILS"
        title={t.ticket_id}
        desc={t.subject}
        action={
          canManageTicket ? (
            <select
              value={t.status}
              disabled={busy}
              onChange={(e) => updateStatus(e.target.value)}
            >
              {statuses.map((s) => (
                <option
                  key={s}
                  value={s}
                  disabled={
                    s === 'Resolved' &&
                    ai?.approval_status !== 'Approved'
                  }
                >
                  {s}
                </option>
              ))}
            </select>
          ) : null
        }
      />

      {err && (
        <div className="alert">
          <AlertCircle size={17} />
          {err}
        </div>
      )}

      <div className="detail-grid">
        <div className="detail-main">

          {/* CUSTOMER ISSUE */}

          <section className="card detail-card">
            <div className="section-head">
              <div>
                <h3>Customer issue</h3>
                <p>
                  Submitted {new Date(t.created_at).toLocaleString()}
                </p>
              </div>

              <Badge>{t.priority}</Badge>
            </div>

            <div className="customer-row">
              <div className="avatar">
                {(t.customer_name || 'Restricted')
                  .split(' ')
                  .map((x) => x[0])
                  .join('')
                  .slice(0, 2)}
              </div>

              <div>
                <b>{t.customer_name || 'Customer details restricted'}</b>
                <small>{t.customer_email || 'Not available for your role'}</small>
              </div>
            </div>

            <h4>{t.subject}</h4>
            <p className="description">{t.description}</p>

            <div className="inline-meta">
              <span>
                Category: <b>{t.category}</b>
              </span>

              <span>
                Status: <Badge>{t.status}</Badge>
              </span>
            </div>
          </section>

          {/* AI RESOLUTION COPILOT */}

          <section className="card detail-card">
            <div className="section-head">
              <div>
                <h3>AI resolution copilot</h3>
                <p>
                  Evidence-grounded analysis with source validation
                </p>
              </div>

              {canManageTicket && (
                <button
                  className="btn primary"
                  disabled={busy}
                  onClick={runAI}
                >
                  <Zap size={16} />
                  {busy ? 'Analyzing...' : 'Run AI analysis'}
                </button>
              )}
            </div>

            {ai ? (
              <>
                {!ai.available && (
                  <div className="alert">
                    AI analysis unavailable. {ai.escalation_reason}
                  </div>
                )}

                <div className="ai-grid">
                  <div>
                    <small>Sentiment</small>
                    <b>{ai.sentiment || 'Unavailable'}</b>
                  </div>

                  <div>
                    <small>Confidence heuristic</small>
                    <b>{ai.confidence}</b>
                  </div>

                  <div>
                    <small>Approval</small>
                    <b>
                      <Badge>{ai.approval_status || 'Pending'}</Badge>
                    </b>
                  </div>
                </div>

                <h4>Issue summary</h4>
                <p className="description">
                  {ai.summary || 'No summary available.'}
                </p>

                <h4>Likely root cause</h4>
                <p className="description">
                  {ai.root_cause || 'Not established'}
                </p>

                <h4>Resolution steps</h4>

                {ai.resolution_steps?.length ? (
                  <ol className="steps">
                    {ai.resolution_steps.map((x, index) => (
                      <li key={index}>{x}</li>
                    ))}
                  </ol>
                ) : (
                  <p className="muted">
                    No verified resolution steps available.
                  </p>
                )}

                {/* CUSTOMER RESPONSE */}

                <div className="section-head">
                  <div>
                    <h4>Customer response draft</h4>
                    <p>
                      Review and edit the response before approval.
                    </p>
                  </div>

                  {canManageTicket && !editMode && canEdit && (
                    <button
                      className="btn secondary"
                      disabled={busy}
                      onClick={startEditing}
                    >
                      <Pencil size={15} />
                      Edit response
                    </button>
                  )}
                </div>

                {canManageTicket && editMode ? (
                  <div className="response-draft">
                    <textarea
                      rows="7"
                      value={editedResponse}
                      onChange={(e) =>
                        setEditedResponse(e.target.value)
                      }
                      disabled={busy}
                      placeholder="Edit customer response..."
                    />

                    <div className="form-footer">
                      <button
                        className="btn secondary"
                        onClick={cancelEditing}
                        disabled={busy}
                      >
                        <X size={15} />
                        Cancel
                      </button>

                      <button
                        className="btn primary"
                        onClick={saveEditedResponse}
                        disabled={busy || !editedResponse.trim()}
                      >
                        <Save size={15} />
                        {busy ? 'Saving...' : 'Save changes'}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="response-draft">
                    {ai.customer_response ||
                      'No customer response generated.'}
                  </div>
                )}

                {/* RETRIEVED SOURCES */}

                <h4>Retrieved sources</h4>

                {ai.sources?.length ? (
                  ai.sources.map((s, index) => (
                    <div
                      className="source"
                      key={`${s.chunk_id}-${index}`}
                    >
                      <FileText size={16} />
                      <span>{s.document_name}</span>
                      <small>{s.chunk_id}</small>
                    </div>
                  ))
                ) : (
                  <p className="muted">
                    No validated sources attached.
                  </p>
                )}

                {/* ESCALATION WARNING */}

                {ai.escalation_required && (
                  <div className="alert">
                    <ShieldAlert size={17} />
                    {ai.escalation_reason ||
                      'Human review required. This ticket cannot be approved automatically.'}
                  </div>
                )}

                {/* APPROVAL ACTIONS */}

                {canManageTicket && (
                  <div className="form-footer">
                    <button
                      className="btn secondary"
                      disabled={busy || t.status === 'Resolved'}
                      onClick={() => updateStatus('In Progress')}
                    >
                      Keep in progress
                    </button>

                    <button
                      className="btn primary"
                      disabled={busy || !canApprove || editMode}
                      onClick={approve}
                      title={
                        ai.escalation_required
                          ? 'Human escalation is required'
                          : ai.approval_status === 'Rejected'
                            ? 'Rejected response cannot be approved'
                            : ai.approval_status === 'Approved'
                              ? 'Already approved'
                              : 'Approve customer response'
                      }
                    >
                      <CheckCircle2 size={16} />

                      {busy
                        ? 'Processing...'
                        : ai.approval_status === 'Approved'
                          ? 'Approved'
                          : ai.approval_status === 'Rejected'
                            ? 'Rejected'
                            : ai.escalation_required
                              ? 'Human review required'
                              : !ai.available
                                ? 'Approval unavailable'
                                : 'Approve response'}
                    </button>
                  </div>
                )}

                {/* REJECTION WORKFLOW */}

                {canManageTicket && canReject && !editMode && (
                  <div className="rejection-section">
                    <h4>Reject AI response</h4>

                    <p className="muted">
                      Provide a reason for rejecting this response.
                    </p>

                    <textarea
                      rows="3"
                      value={rejectionReason}
                      onChange={(e) =>
                        setRejectionReason(e.target.value)
                      }
                      placeholder="Explain why this AI response should be rejected..."
                      disabled={busy}
                    />

                    <div className="form-footer">
                      <button
                        className="btn secondary"
                        onClick={reject}
                        disabled={
                          busy ||
                          rejectionReason.trim().length < 5
                        }
                      >
                        <XCircle size={16} />
                        {busy ? 'Processing...' : 'Reject response'}
                      </button>
                    </div>
                  </div>
                )}

                {ai.approval_status === 'Rejected' && (
                  <div className="alert">
                    <XCircle size={17} />
                    This AI response has been rejected.
                  </div>
                )}

                {ai.approval_status === 'Approved' && (
                  <div className="status-pill">
                    <CheckCircle2 size={16} />
                    Response approved and ticket resolved.
                  </div>
                )}
              </>
            ) : (
              <div className="empty">
                <Zap size={26} />
                <span>
                  Run AI analysis to classify this ticket and retrieve
                  relevant knowledge.
                </span>
              </div>
            )}
          </section>

          {/* INTERNAL NOTES */}

          <section className="card detail-card">
            <h3>Internal notes</h3>

            {canManageTicket && (
              <>
                <textarea
                  rows="3"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="Add an internal note..."
                  disabled={busy}
                />

                <div className="form-footer">
                  <button
                    className="btn secondary"
                    onClick={addNote}
                    disabled={busy || !note.trim()}
                  >
                    {busy ? 'Saving...' : 'Save note'}
                  </button>
                </div>
              </>
            )}

            {t.notes?.length > 0 && (
              <div className="notes-list">
                <h4>Saved notes</h4>

                {t.notes.map((n, index) => (
                  <div className="source" key={index}>
                    <div>
                      <b>{n.author}</b>
                      <p>{n.note}</p>
                      <small>
                        {new Date(n.created_at).toLocaleString()}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* RIGHT SIDEBAR */}

        <aside className="detail-side">

          {/* STATUS TIMELINE */}

          <section className="card detail-card">
            <h3>
              <History size={17} /> Ticket timeline
            </h3>

            {history.length ? (
              history.map((h, index) => (
                <div className="timeline" key={index}>
                  <i />
                  <div>
                    <b>{h.new_status}</b>
                    <small>
                      {h.old_status} â†’ {h.new_status}
                    </small>
                    <small>{h.note || 'Status updated'}</small>
                    <small>
                      {new Date(h.created_at).toLocaleString()}
                    </small>
                  </div>
                </div>
              ))
            ) : (
              <Empty text="No status history available." />
            )}
          </section>

          {/* ACTION AUDIT HISTORY */}

          <section className="card detail-card">
            <h3>
              <History size={17} /> Response action history
            </h3>

            <p className="muted">
              Recorded edits, approvals and rejections.
            </p>

            {actionHistory.length ? (
              actionHistory.map((item) => (
                <div className="timeline" key={item.id}>
                  <i />

                  <div>
                    <b>
                      <Badge
                        tone={item.action.toLowerCase()}
                      >
                        {item.action}
                      </Badge>
                    </b>

                    <small>Actor: {item.actor}</small>

                    {item.reason && (
                      <div className="audit-detail">
                        <small>Reason</small>
                        <p>{item.reason}</p>
                      </div>
                    )}

                    {item.previous_response && (
                      <details className="audit-detail">
                        <summary>Previous response</summary>
                        <p>{item.previous_response}</p>
                      </details>
                    )}

                    {item.new_response && (
                      <details className="audit-detail">
                        <summary>New response</summary>
                        <p>{item.new_response}</p>
                      </details>
                    )}

                    <small>
                      {new Date(item.created_at).toLocaleString()}
                    </small>
                  </div>
                </div>
              ))
            ) : (
              <Empty text="No response actions recorded yet." />
            )}
          </section>

          {/* TICKET PROPERTIES */}

          <section className="card detail-card">
            <h3>Ticket properties</h3>

            <div className="property">
              <small>Ticket ID</small>
              <b>{t.ticket_id}</b>
            </div>

            <div className="property">
              <small>Category</small>
              <b>{t.category}</b>
            </div>

            <div className="property">
              <small>Priority</small>
              <b>{t.priority}</b>
            </div>

            <div className="property">
              <small>Customer email</small>
              <b>{t.customer_email || 'Restricted'}</b>
            </div>
          </section>
        </aside>
      </div>
    </>
  );
}

// --------------------------------------------------
// KNOWLEDGE BASE
// --------------------------------------------------

function Knowledge() {
  const { user } = useAuth();
  const canManageKnowledge = user?.role === 'Admin';
  const [docs, setDocs] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const load = () =>
    api
      .get('/api/knowledge/documents')
      .then((r) => {
        setDocs(r.data);
        setMsg('');
      })
      .catch(() => setMsg('Backend unavailable.'));

  useEffect(() => {
    load();
  }, []);

  async function upload(e) {
    if (!canManageKnowledge) return;
    const file = e.target.files[0];

    if (!file) return;

    const body = new FormData();
    body.append('file', file);

    setBusy(true);
    setMsg('Uploading and indexing document...');

    try {
      const r = await api.post('/api/knowledge/upload', body);

      setMsg(
        `${r.data.filename}: ${r.data.chunk_count} chunks indexed${
          r.data.duplicate ? ' (duplicate skipped)' : ''
        }.`
      );

      await load();
    } catch (e) {
      setMsg(e.response?.data?.detail || 'Ingestion failed.');
    } finally {
      setBusy(false);
      e.target.value = '';
    }
  }

  async function remove(id) {
    if (!canManageKnowledge) return;
    if (!window.confirm('Delete this document and all its vectors?')) {
      return;
    }

    try {
      await api.delete(`/api/knowledge/documents/${id}`);
      await load();
    } catch {
      setMsg('Delete failed.');
    }
  }

  return (
    <>
      <PageHead
        eyebrow="KNOWLEDGE MANAGEMENT"
        title="Knowledge base"
        desc="Manage trusted support documents used as evidence by the AI copilot."
      />

      {canManageKnowledge && (
      <section className="card upload-card">
        <div className="upload-icon">
          <UploadCloud size={24} />
        </div>

        <h3>Upload knowledge documents</h3>

        <p>
          Import support policies, troubleshooting guides and product
          documentation.
        </p>
        <label className="btn primary upload-btn">
          {busy ? 'Indexing...' : 'Choose document'}

          <input
            type="file"
            accept=".pdf,.txt,.md"
            onChange={upload}
            disabled={busy}
          />
        </label>

        <small>PDF, TXT or Markdown Â· Maximum 10 MB</small>

        {msg && <div className="upload-msg">{msg}</div>}
      </section>
      )}

      <section className="card table-card">
        <div className="section-head">
          <div>
            <h3>Indexed documents</h3>
            <p>{docs.length} documents in your knowledge base</p>
          </div>

          <button className="btn secondary" onClick={load}>
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>

        {docs.length ? (
          docs.map((d) => (
            <div className="doc-row" key={d.document_id}>
              <div className="doc-icon">
                <FileText />
              </div>

              <div className="doc-info">
                <b>{d.filename}</b>

                <small>
                  {d.chunk_count} chunks Â· Added{' '}
                  {new Date(d.created_at).toLocaleDateString()}
                </small>
              </div>

              <Badge>{d.status}</Badge>

              {canManageKnowledge && (
                <button
                  className="icon-btn danger"
                  onClick={() => remove(d.document_id)}
                  title="Delete document"
                  aria-label={`Delete ${d.filename}`}
                >
                  <Trash2 size={17} />
                </button>
              )}
            </div>
          ))
        ) : (
          <Empty text="No documents indexed yet. Upload your first guide above." />
        )}
      </section>
    </>
  );
}

// --------------------------------------------------
// ESCALATIONS
// --------------------------------------------------

function Escalations() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);

    try {
      const response = await api.get('/api/agents/escalated');
      setItems(response.data);
      setError('');
    } catch {
      setError('Could not load escalated tickets.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <>
      <PageHead
        eyebrow="HUMAN-IN-THE-LOOP"
        title="Escalated tickets"
        desc="Review critical, unsupported or low-evidence cases before responding."
        action={
          <button
            className="btn secondary"
            onClick={load}
            disabled={loading}
          >
            <RefreshCw size={15} />
            {loading ? 'Loading...' : 'Refresh'}
          </button>
        }
      />

      {error && <div className="alert">{error}</div>}

      <section className="card table-card">
        <TicketTable tickets={items} />
      </section>
    </>
  );
}

// --------------------------------------------------
// SYSTEM HEALTH
// --------------------------------------------------

function SettingsPage() {
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api
      .get('/api/system/status')
      .then((r) => setHealth(r.data))
      .catch(() => setHealth({ api: 'unavailable' }));
  }, []);

  return (
    <>
      <PageHead
        eyebrow="CONFIGURATION"
        title="System health"
        desc="Runtime dependencies and AI configuration status."
      />

      <div className="health-grid">
        {Object.entries(health || {}).map(([k, v]) => (
          <div className="card health-item" key={k}>
            <span>{k.replaceAll('_', ' ')}</span>
            <b>{String(v)}</b>
          </div>
        ))}
      </div>

      <div className="card detail-card">
        <h3>Environment configuration</h3>

        <p className="description">
          Configure GROQ_API_KEY, GROQ_MODEL, QDRANT_PATH,
          SIMILARITY_THRESHOLD and CORS_ORIGINS in backend/.env.
          Never put secrets in the frontend environment.
        </p>
      </div>
    </>
  );
}

// --------------------------------------------------
// PROTECTED ROUTES
// --------------------------------------------------


function ProtectedRoute({ children, allowedRoles }) {
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: {
            pathname: window.location.pathname,
            search: window.location.search,
            hash: window.location.hash,
          },
        }}
      />
    );
  }

  if (
    allowedRoles &&
    !allowedRoles.includes(user?.role)
  ) {
    return <Navigate to="/" replace />;
  }

  return children;
}


// --------------------------------------------------
// APPLICATION ROUTES
// --------------------------------------------------

export default function App() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* Public Login */}
      <Route
        path="/login"
        element={
          isAuthenticated
            ? <Navigate to="/" replace />
            : <Login />
        }
      />

      {/* Protected Dashboard */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Shell>
              <Dashboard />
            </Shell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/tickets"
        element={
          <ProtectedRoute>
            <Shell>
              <Tickets />
            </Shell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/tickets/new"
        element={
          <ProtectedRoute allowedRoles={['Admin', 'Agent']}>
            <Shell>
              <CreateTicket />
            </Shell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/tickets/:id"
        element={
          <ProtectedRoute>
            <Shell>
              <TicketDetail />
            </Shell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/knowledge"
        element={
          <ProtectedRoute>
            <Shell>
              <Knowledge />
            </Shell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/escalations"
        element={
          <ProtectedRoute allowedRoles={['Admin', 'Agent']}>
            <Shell>
              <Escalations />
            </Shell>
          </ProtectedRoute>
        }
      />

      <Route
        path="/settings"
        element={
          <ProtectedRoute allowedRoles={['Admin']}>
            <Shell>
              <SettingsPage />
            </Shell>
          </ProtectedRoute>
        }
      />

      <Route
        path="*"
        element={
          <Navigate
            to={isAuthenticated ? "/" : "/login"}
            replace
          />
        }
      />
    </Routes>
  );
}