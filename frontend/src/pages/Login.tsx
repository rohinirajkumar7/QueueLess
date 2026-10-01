import {useState} from 'react';
import type {FormEvent} from 'react';
import {Link, useNavigate, useParams} from 'react-router-dom';
import {api, apiError} from '../services/api';
import {useAuth, type Role} from '../store/auth';
import {Icon} from '../components/Icons';

const configs = {
  customer: {
    role: 'CUSTOMER' as Role,
    title: 'Customer sign in',
    subtitle: 'Find a service, join a queue and track your turn.',
    icon: 'user' as const,
  },
  staff: {
    role: 'STAFF' as Role,
    title: 'Staff sign in',
    subtitle: 'Operate assigned queues and serve customers efficiently.',
    icon: 'users' as const,
  },
  organization: {
    role: 'ORG_ADMIN' as Role,
    title: 'Organization admin',
    subtitle: 'Manage your organization, services, staff and analytics.',
    icon: 'building' as const,
  },
};

export default function Login() {
  const {type = ''} = useParams();
  const navigate = useNavigate();
  const setUser = useAuth((s) => s.setUser);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (!type) {
    return (
      <div className="page-wrap py-16">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-bold uppercase tracking-[.16em] text-indigo-600">
            Welcome back
          </p>
          <h1 className="mt-2 text-4xl font-black">
            Choose your QueueLess portal
          </h1>
          <p className="mt-3 text-slate-500">
            Each account type gets a focused dashboard and permissions.
          </p>
        </div>

        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {Object.entries(configs).map(([key, c]) => (
            <Link
              key={key}
              to={`/login/${key}`}
              className="card group p-6 transition hover:-translate-y-1 hover:border-indigo-200 hover:shadow-xl"
            >
              <span className="grid h-12 w-12 place-items-center rounded-xl bg-indigo-50 text-indigo-600">
                <Icon name={c.icon} />
              </span>
              <h2 className="mt-6 text-xl font-extrabold">{c.title}</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {c.subtitle}
              </p>
              <span className="mt-6 inline-flex items-center gap-2 text-sm font-bold text-indigo-600">
                Continue <Icon name="arrow" size={16} />
              </span>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  const c = configs[type as keyof typeof configs] || configs.customer;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const r = await api.post('/auth/login', {
        email,
        password,
        role: c.role,
      });

      localStorage.setItem('access_token', r.data.access_token);

      if (r.data.refresh_token) {
        localStorage.setItem('refresh_token', r.data.refresh_token);
      }

      const me = r.data.user || (await api.get('/auth/me')).data;
      setUser(me);

      if (me.role === 'CUSTOMER') navigate('/dashboard');
      else if (me.role === 'STAFF') navigate('/staff');
      else navigate('/admin');
    } catch (err) {
      setError(apiError(err, 'Login failed'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-wrap py-10 sm:py-20">
      <div className="mx-auto grid max-w-5xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl md:grid-cols-2">
        <div className="hidden bg-slate-950 p-10 text-white md:block">
          <span className="grid h-12 w-12 place-items-center rounded-xl bg-indigo-500">
            <Icon name={c.icon} size={22} />
          </span>

          <p className="mt-10 text-sm font-bold uppercase tracking-[.16em] text-indigo-300">
            QueueLess {type} portal
          </p>

          <h2 className="mt-3 text-4xl font-black">
            A dashboard built for your role.
          </h2>

          <p className="mt-4 leading-7 text-slate-400">
            {c.subtitle}
          </p>
        </div>

        <div className="p-7 sm:p-10">
          <Link
            to="/login"
            className="text-sm font-bold text-slate-500 hover:text-slate-900"
          >
            ← All portals
          </Link>

          <h1 className="mt-8 text-3xl font-black">{c.title}</h1>

          <p className="mt-2 text-sm text-slate-500">
            {c.subtitle}
          </p>

          {error && (
            <div className="mt-5 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700">
              {error}
            </div>
          )}

          <form onSubmit={submit} className="mt-7 space-y-5">
            <div>
              <label className="label">Email address</label>
              <input
                className="input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div>
              <div className="flex justify-between">
                <label className="label">Password</label>
              </div>

              <input
                className="input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            <div className="flex justify-end">
              <Link
                to="/forgot-password"
                className="text-sm font-bold text-indigo-600 hover:text-indigo-500"
              >
                Forgot password?
              </Link>
            </div>

            <button
              disabled={loading}
              className="btn btn-primary w-full py-3.5"
            >
              {loading ? 'Signing in...' : 'Sign in'}{' '}
              <Icon name="arrow" size={16} />
            </button>
          </form>

          {type === 'customer' && (
            <p className="mt-6 text-sm text-slate-500">
              New customer?{' '}
              <Link
                className="font-bold text-indigo-600"
                to="/register"
              >
                Create an account
              </Link>
            </p>
          )}

          {type === 'organization' && (
            <p className="mt-6 text-sm text-slate-500">
              Launching a service?{' '}
              <Link
                className="font-bold text-indigo-600"
                to="/register/organization"
              >
                Create an organization
              </Link>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
