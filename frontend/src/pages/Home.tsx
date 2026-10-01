import {Link} from 'react-router-dom';
import {Icon} from '../components/Icons';

function HeroIllustration() {
  return (
    <div className="relative mx-auto w-full max-w-md animate-float">
      <svg viewBox="0 0 420 360" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full drop-shadow-2xl">
        <defs>
          <linearGradient id="g1" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#5eead4" />
            <stop offset="100%" stopColor="#0d9488" />
          </linearGradient>
          <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ffffff" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#f0fdfa" stopOpacity="0.9" />
          </linearGradient>
          <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="12" stdDeviation="16" floodColor="#0f766e" floodOpacity="0.25" />
          </filter>
        </defs>
        {/* Background shape */}
        <ellipse cx="210" cy="300" rx="140" ry="28" fill="#0f766e" opacity="0.15" />
        {/* Main phone-like card */}
        <rect x="90" y="30" width="240" height="300" rx="28" fill="url(#g2)" filter="url(#soft)" stroke="#ccfbf1" strokeWidth="2" />
        {/* Header bar */}
        <rect x="110" y="52" width="200" height="36" rx="12" fill="#0d9488" />
        <circle cx="128" cy="70" r="6" fill="#99f6e4" />
        <rect x="142" y="64" width="90" height="12" rx="4" fill="#ccfbf1" opacity="0.9" />
        {/* Token card */}
        <rect x="118" y="110" width="184" height="100" rx="16" fill="url(#g1)" />
        <text x="210" y="148" textAnchor="middle" fill="white" fontSize="13" fontWeight="700" fontFamily="system-ui">YOUR TOKEN</text>
        <text x="210" y="186" textAnchor="middle" fill="white" fontSize="42" fontWeight="800" fontFamily="system-ui">A-014</text>
        {/* Position rows */}
        <rect x="118" y="230" width="184" height="18" rx="6" fill="#e2e8f0" />
        <rect x="118" y="230" width="110" height="18" rx="6" fill="#14b8a6" />
        <rect x="118" y="260" width="184" height="18" rx="6" fill="#e2e8f0" />
        <rect x="118" y="260" width="70" height="18" rx="6" fill="#5eead4" />
        <text x="118" y="308" fill="#64748b" fontSize="11" fontFamily="system-ui" fontWeight="600">2 people ahead · ~8 min</text>
        {/* Floating badge */}
        <g transform="translate(300,90)">
          <rect width="90" height="44" rx="12" fill="#fff" stroke="#ccfbf1" strokeWidth="1.5" filter="url(#soft)" />
          <circle cx="22" cy="22" r="10" fill="#d1fae5" />
          <path d="M17 22 l3 3 6-7" stroke="#0d9488" strokeWidth="2" fill="none" strokeLinecap="round" />
          <text x="38" y="20" fill="#0f766e" fontSize="10" fontWeight="700" fontFamily="system-ui">Live</text>
          <text x="38" y="32" fill="#64748b" fontSize="9" fontFamily="system-ui">updates</text>
        </g>
      </svg>
    </div>
  );
}

const features = [
  {
    icon: 'queue' as const,
    title: 'Join remotely',
    body: 'Take a digital token before you arrive and track your place in line from your phone.',
  },
  {
    icon: 'clock' as const,
    title: 'Know your wait',
    body: 'See how many people are ahead and get a realistic estimate — no more guessing.',
  },
  {
    icon: 'dashboard' as const,
    title: 'Run operations',
    body: 'Staff and admins get focused tools to call, serve, and measure every queue.',
  },
] as const;

const portals = [
  {
    to: '/login/customer',
    title: 'Customer',
    desc: 'Join queues, book appointments, get notified.',
    icon: 'user' as const,
    accent: 'from-teal-500 to-teal-700',
  },
  {
    to: '/login/staff',
    title: 'Staff',
    desc: 'Call next, start service, complete tickets.',
    icon: 'users' as const,
    accent: 'from-cyan-500 to-teal-600',
  },
  {
    to: '/login/organization',
    title: 'Organization',
    desc: 'Manage services, staff, and analytics.',
    icon: 'building' as const,
    accent: 'from-slate-700 to-slate-900',
  },
] as const;

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-slate-900 to-teal-950" />
        <div className="absolute -left-32 top-20 h-72 w-72 rounded-full bg-teal-500/20 blur-3xl" />
        <div className="absolute -right-20 bottom-10 h-80 w-80 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="page-wrap relative grid items-center gap-12 py-16 lg:grid-cols-2 lg:py-24">
          <div>
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs font-bold uppercase tracking-[0.14em] text-teal-200">
              <Icon name="spark" size={14} />
              Less waiting. Better service.
            </div>
            <h1 className="text-4xl font-black leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-6xl">
              The queue should work{' '}
              <span className="bg-gradient-to-r from-teal-300 to-cyan-300 bg-clip-text text-transparent">around you.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-7 text-slate-300 sm:text-lg">
              QueueLess turns physical waiting lines into a real-time digital experience for customers, staff, and service organizations.
            </p>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Link to="/login/customer" className="btn btn-primary px-6 py-3.5 text-base">
                Join a queue <Icon name="arrow" />
              </Link>
              <Link
                to="/login/organization"
                className="btn border border-white/15 bg-white/5 px-6 py-3.5 text-base text-white hover:bg-white/10"
              >
                Run an organization <Icon name="building" />
              </Link>
            </div>
            <div className="mt-10 flex flex-wrap gap-x-6 gap-y-3 text-sm text-slate-400">
              <span className="flex items-center gap-2">
                <Icon name="check" size={15} className="text-teal-400" /> Live queue updates
              </span>
              <span className="flex items-center gap-2">
                <Icon name="check" size={15} className="text-teal-400" /> Role-based access
              </span>
              <span className="flex items-center gap-2">
                <Icon name="check" size={15} className="text-teal-400" /> Appointments
              </span>
            </div>
          </div>
          <HeroIllustration />
        </div>
      </section>

      {/* Portals */}
      <section className="page-wrap py-16">
        <div className="max-w-2xl">
          <p className="text-sm font-bold uppercase tracking-[0.14em] text-teal-600">Choose your portal</p>
          <h2 className="mt-2 text-3xl font-black tracking-tight text-slate-900 sm:text-4xl">
            Built for every role on the floor.
          </h2>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {portals.map((p) => (
            <Link
              key={p.to}
              to={p.to}
              className="portal-card card group p-6 transition duration-200 hover:-translate-y-1 hover:border-teal-200 hover:shadow-xl hover:shadow-teal-900/5"
            >
              <span className={`mb-6 grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br ${p.accent} text-white shadow-lg`}>
                <Icon name={p.icon} size={20} />
              </span>
              <h3 className="text-xl font-extrabold text-slate-900">{p.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-500">{p.desc}</p>
              <span className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-teal-600 group-hover:gap-3 transition-all">
                Continue <Icon name="arrow" size={16} />
              </span>
            </Link>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="page-wrap pb-8">
        <div className="grid gap-5 md:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="card p-6">
              <span className="mb-6 grid h-11 w-11 place-items-center rounded-xl bg-teal-50 text-teal-700">
                <Icon name={f.icon} />
              </span>
              <h3 className="text-lg font-extrabold text-slate-900">{f.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-500">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA band */}
      <section className="page-wrap py-12 pb-16">
        <div className="illust-card p-8 sm:p-10">
          <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-white/10" />
          <div className="absolute -bottom-20 left-20 h-40 w-40 rounded-full bg-cyan-300/20" />
          <div className="relative flex flex-col justify-between gap-7 md:flex-row md:items-center">
            <div>
              <p className="text-sm font-bold uppercase tracking-[0.14em] text-teal-100">For service teams</p>
              <h2 className="mt-2 text-3xl font-black text-white">Stop managing queues on paper.</h2>
              <p className="mt-2 max-w-xl text-teal-50/90">
                Create services, assign staff, call customers, and measure the operation from one place.
              </p>
            </div>
            <Link to="/register/organization" className="btn shrink-0 whitespace-nowrap bg-white px-6 py-3.5 text-slate-900 shadow-lg hover:bg-teal-50">
              Create organization <Icon name="arrow" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
