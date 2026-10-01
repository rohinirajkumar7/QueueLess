import {useEffect, useState} from 'react';
import {Link, NavLink, Outlet, useLocation, useNavigate} from 'react-router-dom';
import {useAuth} from '../store/auth';
import {api} from '../services/api';
import {Icon} from './Icons';

const roleLabel = {
  CUSTOMER: 'Customer',
  STAFF: 'Staff',
  ORG_ADMIN: 'Organization Admin',
} as const;

type NavItem = {to: string; label: string; icon: 'dashboard' | 'search' | 'calendar' | 'bell' | 'queue' | 'users' | 'building'};

function itemsForRole(role?: string): NavItem[] {
  if (role === 'CUSTOMER') {
    return [
      {to: '/dashboard', label: 'Overview', icon: 'dashboard'},
      {to: '/organizations', label: 'Find service', icon: 'search'},
      {to: '/appointments', label: 'Appointments', icon: 'calendar'},
      {to: '/notifications', label: 'Notifications', icon: 'bell'},
    ];
  }
  if (role === 'STAFF') {
    return [{to: '/staff', label: 'Operations', icon: 'queue'}];
  }
  if (role === 'ORG_ADMIN') {
    return [
      {to: '/admin', label: 'Organization', icon: 'building'},
      {to: '/staff', label: 'Live queues', icon: 'queue'},
    ];
  }
  return [];
}

function navClass({isActive}: {isActive: boolean}) {
  return [
    'flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-all duration-200',
    isActive
      ? 'bg-teal-600 text-white shadow-md shadow-teal-600/25'
      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  ].join(' ');
}

function mobileNavClass({isActive}: {isActive: boolean}) {
  return [
    'flex items-center gap-3 rounded-2xl px-4 py-3.5 text-[15px] font-semibold transition-all',
    isActive ? 'bg-teal-600 text-white shadow-lg shadow-teal-600/20' : 'bg-slate-50 text-slate-700 hover:bg-slate-100',
  ].join(' ');
}

export default function Layout() {
  const {user, setUser, logout} = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (!localStorage.getItem('access_token')) return;
    if (user) return;
    api
      .get('/auth/me')
      .then((r) => setUser(r.data))
      .catch(() => {});
  }, [user, setUser]);

  useEffect(() => setOpen(false), [location.pathname]);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  const home =
    user?.role === 'CUSTOMER' ? '/dashboard' : user?.role === 'STAFF' ? '/staff' : user?.role === 'ORG_ADMIN' ? '/admin' : '/';

  const navItems = itemsForRole(user?.role);
  const canGoBack = location.pathname !== '/' && location.pathname !== home;

  function signOut() {
    logout();
    navigate('/');
  }

  function goBack() {
    if (window.history.length > 1) navigate(-1);
    else navigate(home);
  }

  function onLogoClick(e: { preventDefault: () => void }) {
    e.preventDefault();
    if (location.pathname === home || location.pathname === '/') {
      // Already home → soft reload of current view
      navigate(0);
    } else {
      navigate(home);
    }
  }

  return (
    <div className="app-shell">
      <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/85 backdrop-blur-xl">
        <div className="page-wrap flex min-h-[68px] items-center justify-between gap-3 py-2.5">
          <div className="flex items-center gap-2 sm:gap-3">
            {canGoBack && (
              <button
                type="button"
                onClick={goBack}
                className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:border-teal-200 hover:bg-teal-50 hover:text-teal-700"
                aria-label="Go back"
                title="Go back"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 18l-6-6 6-6" />
                </svg>
              </button>
            )}

            <a href={home} onClick={onLogoClick} className="flex items-center gap-3 rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-teal-500">
              <span className="relative grid h-10 w-10 place-items-center overflow-hidden rounded-xl bg-gradient-to-br from-teal-500 to-teal-700 text-sm font-black tracking-tight text-white shadow-lg shadow-teal-600/30">
                <span className="relative z-10">QL</span>
                <span className="absolute -right-2 -top-2 h-8 w-8 rounded-full bg-white/15" />
              </span>
              <span>
                <span className="block text-lg font-extrabold tracking-tight text-slate-900">QueueLess</span>
                <span className="hidden text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400 sm:block">
                  Digital queue platform
                </span>
              </span>
            </a>
          </div>

          {/* Desktop nav */}
          <nav className="hidden items-center gap-1 md:flex">
            {user ? (
              <>
                {navItems.map((item) => (
                  <NavLink key={item.to} to={item.to} className={navClass}>
                    <Icon name={item.icon} size={16} />
                    {item.label}
                  </NavLink>
                ))}
                <div className="ml-3 flex items-center gap-3 border-l border-slate-200 pl-4">
                  <div className="hidden text-right lg:block">
                    <p className="text-sm font-bold text-slate-800">{user.name}</p>
                    <p className="text-[11px] font-semibold text-teal-600">{roleLabel[user.role]}</p>
                  </div>
                  <button type="button" className="btn btn-ghost !px-3" onClick={signOut}>
                    <Icon name="logOut" size={17} />
                    Logout
                  </button>
                </div>
              </>
            ) : (
              <>
                <Link to="/login" className="btn btn-ghost">
                  Sign in
                </Link>
                <Link to="/register" className="btn btn-primary">
                  Get started
                </Link>
              </>
            )}
          </nav>

          {/* Mobile menu button */}
          <button
            type="button"
            className="grid h-11 w-11 place-items-center rounded-xl border border-slate-200 bg-white text-slate-700 shadow-sm transition hover:border-teal-200 hover:bg-teal-50 md:hidden"
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? 'Close menu' : 'Open menu'}
            aria-expanded={open}
          >
            <Icon name={open ? 'close' : 'menu'} size={20} />
          </button>
        </div>
      </header>

      {/* Mobile drawer */}
      {open && (
        <>
          <div className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm md:hidden" onClick={() => setOpen(false)} />
          <aside className="fixed inset-y-0 right-0 z-50 flex w-[min(100%,320px)] flex-col bg-white shadow-2xl md:hidden animate-slide-in">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div>
                <p className="text-sm font-bold text-slate-900">{user?.name || 'Menu'}</p>
                <p className="text-xs font-semibold text-teal-600">
                  {user ? roleLabel[user.role] : 'Welcome to QueueLess'}
                </p>
              </div>
              <button
                type="button"
                className="grid h-9 w-9 place-items-center rounded-lg text-slate-500 hover:bg-slate-100"
                onClick={() => setOpen(false)}
                aria-label="Close"
              >
                <Icon name="close" size={18} />
              </button>
            </div>

            <nav className="flex-1 space-y-2 overflow-y-auto px-4 py-5">
              {user ? (
                <>
                  {navItems.map((item) => (
                    <NavLink key={item.to} to={item.to} className={mobileNavClass}>
                      <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/20">
                        <Icon name={item.icon} size={18} />
                      </span>
                      {item.label}
                    </NavLink>
                  ))}
                  <div className="my-4 h-px bg-slate-100" />
                  <button
                    type="button"
                    onClick={signOut}
                    className="flex w-full items-center gap-3 rounded-2xl bg-rose-50 px-4 py-3.5 text-[15px] font-semibold text-rose-700 transition hover:bg-rose-100"
                  >
                    <span className="grid h-9 w-9 place-items-center rounded-xl bg-rose-100">
                      <Icon name="logOut" size={18} />
                    </span>
                    Sign out
                  </button>
                </>
              ) : (
                <>
                  <Link to="/login" className="btn btn-soft w-full justify-center py-3.5">
                    Sign in
                  </Link>
                  <Link to="/register" className="btn btn-primary w-full justify-center py-3.5">
                    Get started
                  </Link>
                  <Link to="/login/customer" className="mt-2 block text-center text-sm font-semibold text-teal-600">
                    Customer portal →
                  </Link>
                </>
              )}
            </nav>

            <div className="border-t border-slate-100 px-5 py-4">
              <p className="text-xs font-medium text-slate-400">QueueLess · Real-time queues</p>
            </div>
          </aside>
        </>
      )}

      <main className="min-h-[calc(100vh-68px-88px)]">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="page-wrap flex flex-col items-start justify-between gap-3 py-8 text-sm text-slate-500 sm:flex-row sm:items-center">
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-teal-600 text-[10px] font-black text-white">QL</span>
            <span>© 2026 QueueLess</span>
          </div>
          <span className="text-slate-400">Real-time queues · Appointments · Operations</span>
        </div>
      </footer>
    </div>
  );
}
