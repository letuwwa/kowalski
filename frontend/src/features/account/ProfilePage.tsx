import { useAuth } from '../auth/authContext';

export function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;
  return (
    <section className="profile-page" aria-labelledby="profile-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Your account</p>
          <h1 id="profile-title">Profile</h1>
          <p>The account associated with your scans and reports.</p>
        </div>
      </header>
      <div className="dashboard-panel">
        <h2>Account details</h2>
        <dl className="account">
          <div>
            <dt>Name</dt>
            <dd>
              {user.first_name} {user.last_name}
            </dd>
          </div>
          <div>
            <dt>Username</dt>
            <dd>{user.username}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{user.email}</dd>
          </div>
          <div>
            <dt>Role</dt>
            <dd>{user.role}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
