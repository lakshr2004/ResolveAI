
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Users,
  UserPlus,
  Search,
  RefreshCw,
  ShieldCheck,
  UserCheck,
  UserX,
  X,
  AlertCircle,
  CheckCircle2,
  LoaderCircle,
} from 'lucide-react';

import api from '../services/api';
import { useAuth } from '../context/AuthContext';

function getErrorMessage(error) {
  const detail = error.response?.data?.detail;

  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join(', ');
  }

  return error.message || 'Something went wrong. Please try again.';
}

function initials(name = '') {
  return name
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
}

export default function UserManagement() {
  const { user: currentUser } = useAuth();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('All');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [updatingId, setUpdatingId] = useState(null);

  const [form, setForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'Agent',
  });

  const fetchUsers = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    setError('');

    try {
      const response = await api.get('/api/users');
      setUsers(response.data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();

    return users.filter((item) => {
      const matchesSearch =
        !query ||
        item.full_name.toLowerCase().includes(query) ||
        item.email.toLowerCase().includes(query);

      const matchesRole =
        roleFilter === 'All' || item.role === roleFilter;

      const matchesStatus =
        statusFilter === 'All' ||
        (statusFilter === 'Active' ? item.is_active : !item.is_active);

      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [users, search, roleFilter, statusFilter]);

  const stats = useMemo(() => ({
    total: users.length,
    agents: users.filter((item) => item.role === 'Agent').length,
    viewers: users.filter((item) => item.role === 'Viewer').length,
    active: users.filter((item) => item.is_active).length,
  }), [users]);

  const handleCreateUser = async (event) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    setCreating(true);

    try {
      await api.post('/api/users', {
        full_name: form.full_name.trim(),
        email: form.email.trim().toLowerCase(),
        password: form.password,
        role: form.role,
      });

      setForm({
        full_name: '',
        email: '',
        password: '',
        role: 'Agent',
      });

      setShowCreateForm(false);
      setSuccess('User created successfully.');
      await fetchUsers();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setCreating(false);
    }
  };

  const handleRoleChange = async (targetUser, newRole) => {
    if (targetUser.role === newRole || updatingId !== null) return;

    const confirmed = window.confirm(
      `Change ${targetUser.full_name}'s role to ${newRole}?`
    );

    if (!confirmed) return;

    setError('');
    setSuccess('');
    setUpdatingId(targetUser.id);

    try {
      const response = await api.patch(
        `/api/users/${targetUser.id}/role`,
        { role: newRole }
      );

      setUsers((previous) =>
        previous.map((item) =>
          item.id === targetUser.id ? response.data : item
        )
      );

      setSuccess(`${targetUser.full_name}'s role updated.`);
    } catch (err) {
      setError(getErrorMessage(err));
      await fetchUsers();
    } finally {
      setUpdatingId(null);
    }
  };

  const handleStatusChange = async (targetUser) => {
    const nextStatus = !targetUser.is_active;
    const action = nextStatus ? 'activate' : 'deactivate';

    if (updatingId !== null) return;

    const confirmed = window.confirm(
      `Are you sure you want to ${action} ${targetUser.full_name}'s account?`
    );

    if (!confirmed) return;

    setError('');
    setSuccess('');
    setUpdatingId(targetUser.id);

    try {
      const response = await api.patch(
        `/api/users/${targetUser.id}/status`,
        { is_active: nextStatus }
      );

      setUsers((previous) =>
        previous.map((item) =>
          item.id === targetUser.id ? response.data : item
        )
      );

      setSuccess(
        `${targetUser.full_name}'s account ${nextStatus ? 'activated' : 'deactivated'}.`
      );
    } catch (err) {
      setError(getErrorMessage(err));
      await fetchUsers();
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <div className="user-management">
      <div className="page-head">
        <div>
          <div className="eyebrow">ADMINISTRATION</div>
          <h1>User management</h1>
          <p>
            Manage support team accounts, permissions and access status.
          </p>
        </div>

        <div className="user-page-actions">
          <button
            className="btn secondary"
            onClick={() => fetchUsers(true)}
            disabled={refreshing || loading}
          >
            <RefreshCw size={14} className={refreshing ? 'user-spin' : ''} />
            Refresh
          </button>

          <button
            className="btn primary"
            onClick={() => {
              setError('');
              setSuccess('');
              setShowCreateForm(true);
            }}
          >
            <UserPlus size={15} />
            Add user
          </button>
        </div>
      </div>

      {error && (
        <div className="alert user-message">
          <AlertCircle size={16} />
          {error}
          <button
            className="user-message-close"
            onClick={() => setError('')}
            aria-label="Dismiss error"
          >
            <X size={15} />
          </button>
        </div>
      )}

      {success && (
        <div className="user-success user-message">
          <CheckCircle2 size={16} />
          {success}
          <button
            className="user-message-close"
            onClick={() => setSuccess('')}
            aria-label="Dismiss message"
          >
            <X size={15} />
          </button>
        </div>
      )}

      <div className="user-stats-grid">
        <div className="card user-stat-card">
          <div className="user-stat-icon purple"><Users size={18} /></div>
          <div>
            <small>Total users</small>
            <strong>{stats.total}</strong>
          </div>
        </div>

        <div className="card user-stat-card">
          <div className="user-stat-icon blue"><ShieldCheck size={18} /></div>
          <div>
            <small>Agents</small>
            <strong>{stats.agents}</strong>
          </div>
        </div>

        <div className="card user-stat-card">
          <div className="user-stat-icon orange"><Users size={18} /></div>
          <div>
            <small>Viewers</small>
            <strong>{stats.viewers}</strong>
          </div>
        </div>

        <div className="card user-stat-card">
          <div className="user-stat-icon green"><UserCheck size={18} /></div>
          <div>
            <small>Active accounts</small>
            <strong>{stats.active}</strong>
          </div>
        </div>
      </div>

      <section className="card user-table-card">
        <div className="user-table-heading">
          <div>
            <h3>Team members</h3>
            <p>{filteredUsers.length} of {users.length} users</p>
          </div>
        </div>

        <div className="user-filters">
          <div className="searchbox">
            <Search size={16} />
            <input
              type="search"
              placeholder="Search by name or email..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <select
            aria-label="Filter by role"
            value={roleFilter}
            onChange={(event) => setRoleFilter(event.target.value)}
          >
            <option value="All">All roles</option>
            <option value="Admin">Admin</option>
            <option value="Agent">Agent</option>
            <option value="Viewer">Viewer</option>
          </select>

          <select
            aria-label="Filter by account status"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="All">All statuses</option>
            <option value="Active">Active</option>
            <option value="Inactive">Inactive</option>
          </select>
        </div>

        <div className="table-scroll">
          <table className="user-table">
            <thead>
              <tr>
                <th>USER</th>
                <th>ROLE</th>
                <th>STATUS</th>
                <th>ACCESS CONTROL</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="4">
                    <div className="user-loading">
                      <LoaderCircle size={19} className="user-spin" />
                      Loading users...
                    </div>
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan="4">
                    <div className="empty">
                      <Users size={24} />
                      <b>No users found</b>
                      <span>Try changing your search or filters.</span>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredUsers.map((item) => {
                  const isCurrentUser = item.id === currentUser?.id;
                  const isAdmin = item.role === 'Admin';
                  const isUpdating = updatingId === item.id;

                  return (
                    <tr key={item.id}>
                      <td>
                        <div className="user-identity">
                          <div className="user-avatar">
                            {initials(item.full_name)}
                          </div>
                          <div>
                            <b>{item.full_name}</b>
                            <small>{item.email}</small>
                            {isCurrentUser && (
                              <span className="user-you-label">YOU</span>
                            )}
                          </div>
                        </div>
                      </td>

                      <td>
                        <span className={`badge user-role-${item.role.toLowerCase()}`}>
                          {item.role}
                        </span>
                      </td>

                      <td>
                        <span className={`badge ${item.is_active ? 'approved' : 'rejected'}`}>
                          {item.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>

                      <td>
                        <div className="user-controls">
                          <select
                            aria-label={`Change role for ${item.full_name}`}
                            value={item.role}
                            disabled={isCurrentUser || isAdmin || isUpdating}
                            onChange={(event) =>
                              handleRoleChange(item, event.target.value)
                            }
                          >
                            <option value="Agent">Agent</option>
                            <option value="Viewer">Viewer</option>
                          </select>

                          <button
                            className={`user-status-btn ${item.is_active ? 'deactivate' : 'activate'}`}
                            onClick={() => handleStatusChange(item)}
                            disabled={isCurrentUser || isUpdating}
                            title={
                              isCurrentUser
                                ? 'You cannot deactivate your own account'
                                : isAdmin
                                  ? 'Admin account status is managed separately'
                                  : item.is_active
                                    ? 'Deactivate account'
                                    : 'Activate account'
                            }
                          >
                            {isUpdating ? (
                              <LoaderCircle size={14} className="user-spin" />
                            ) : item.is_active ? (
                              <><UserX size={14} /> Deactivate</>
                            ) : (
                              <><UserCheck size={14} /> Activate</>
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {showCreateForm && (
        <div
          className="user-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !creating) {
              setShowCreateForm(false);
            }
          }}
        >
          <section
            className="card user-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-user-title"
          >
            <div className="user-modal-header">
              <div>
                <div className="eyebrow">NEW ACCOUNT</div>
                <h2 id="create-user-title">Create team member</h2>
                <p>Add an Agent or Viewer to your workspace.</p>
              </div>

              <button
                className="icon-btn"
                onClick={() => setShowCreateForm(false)}
                disabled={creating}
                aria-label="Close dialog"
              >
                <X size={19} />
              </button>
            </div>

            <form onSubmit={handleCreateUser}>
              <div className="user-form-fields">
                <label className="field">
                  Full name
                  <input
                    type="text"
                    required
                    minLength={2}
                    maxLength={120}
                    autoComplete="name"
                    placeholder="Enter full name"
                    value={form.full_name}
                    onChange={(event) =>
                      setForm({ ...form, full_name: event.target.value })
                    }
                  />
                </label>

                <label className="field">
                  Email address
                  <input
                    type="email"
                    required
                    maxLength={255}
                    autoComplete="email"
                    placeholder="name@example.com"
                    value={form.email}
                    onChange={(event) =>
                      setForm({ ...form, email: event.target.value })
                    }
                  />
                </label>

                <label className="field">
                  Temporary password
                  <input
                    type="password"
                    required
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                    placeholder="Minimum 12 characters"
                    value={form.password}
                    onChange={(event) =>
                      setForm({ ...form, password: event.target.value })
                    }
                  />
                  <small className="user-field-hint">
                    Share this password securely with the new user.
                  </small>
                </label>

                <label className="field">
                  Account role
                  <select
                    value={form.role}
                    onChange={(event) =>
                      setForm({ ...form, role: event.target.value })
                    }
                  >
                    <option value="Agent">Agent</option>
                    <option value="Viewer">Viewer</option>
                  </select>
                </label>
              </div>

              <div className="user-modal-footer">
                <button
                  type="button"
                  className="btn secondary"
                  onClick={() => setShowCreateForm(false)}
                  disabled={creating}
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="btn primary"
                  disabled={creating}
                >
                  {creating ? (
                    <><LoaderCircle size={15} className="user-spin" /> Creating...</>
                  ) : (
                    <><UserPlus size={15} /> Create user</>
                  )}
                </button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
}
