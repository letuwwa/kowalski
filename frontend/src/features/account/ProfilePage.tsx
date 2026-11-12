import { useAuth } from '../auth/authContext';

export function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <section aria-labelledby="profile-title">
      <h1 id="profile-title">Profile</h1>
      <dl className="account">
        <div><dt>Name</dt><dd>{user.first_name} {user.last_name}</dd></div>
        <div><dt>Username</dt><dd>{user.username}</dd></div>
        <div><dt>Email</dt><dd>{user.email}</dd></div>
      </dl>
    </section>
  );
}
