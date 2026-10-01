import {useEffect, useState} from 'react';
import {api, apiError} from '../services/api';
import {useAuth} from '../store/auth';

interface QueueInfo {
  queue_id: string;
  service_id: string;
  service_name: string;
  current_token: string | null;
  waiting: number;
}

interface ActiveToken {
  id: string;
  token_number: number;
  token_code: string;
  status: string;
  user_id?: string;
}

export default function Staff() {
  const user = useAuth((s) => s.user);
  const [queues, setQueues] = useState<QueueInfo[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [activeToken, setActiveToken] = useState<ActiveToken | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function loadQueues() {
    try {
      setError('');
      // Official staff-assigned queues endpoint
      const r = await api.get('/analytics/queues');
      const rows: QueueInfo[] = Array.isArray(r.data) ? r.data : [];
      setQueues(rows);
      if (!selected && rows.length) {
        setSelected(rows[0].queue_id);
      }
      // Keep selection if still present
      if (selected && !rows.find((q) => q.queue_id === selected) && rows.length) {
        setSelected(rows[0].queue_id);
      }
    } catch (err) {
      setError(apiError(err, 'Failed to load assigned queues'));
      setQueues([]);
    }
  }

  useEffect(() => {
    loadQueues();
    const t = setInterval(loadQueues, 8000);
    return () => clearInterval(t);
  }, []);

  // When queue selection changes, clear previous active token if queue changed
  useEffect(() => {
    setActiveToken(null);
  }, [selected]);

  const current = queues.find((q) => q.queue_id === selected);

  async function callNext() {
    if (!selected) return;
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const r = await api.post(`/queues/${selected}/call-next`);
      setActiveToken(r.data);
      setMessage(`Called ${r.data.token_code}`);
      await loadQueues();
    } catch (err) {
      setError(apiError(err, 'Call next failed'));
    } finally {
      setLoading(false);
    }
  }

  async function tokenAction(action: 'start' | 'complete' | 'skip' | 'recall', label: string) {
    if (!activeToken?.id) {
      setError('Call next first to get an active token');
      return;
    }
    setLoading(true);
    setError('');
    setMessage('');
    try {
      const r = await api.post(`/tokens/${activeToken.id}/${action}`);
      setActiveToken(r.data);
      setMessage(`${label} · ${r.data.token_code} is now ${r.data.status}`);
      if (action === 'complete' || action === 'skip') {
        // Clear after finishing so next call-next is clean
        setTimeout(() => setActiveToken(null), 1500);
      }
      await loadQueues();
    } catch (err) {
      setError(apiError(err, `${label} failed`));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-wrap py-10">
      <div className="mb-8">
        <p className="text-sm font-bold uppercase tracking-[.16em] text-sky-600">Staff portal</p>
        <h1 className="mt-2 text-3xl font-black">Hello, {user?.name || 'Staff'}</h1>
        <p className="mt-2 text-slate-500">Operate your assigned queues — call next, start service, complete or skip.</p>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-700">
          {error}
        </div>
      )}
      {message && (
        <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-700">
          {message}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="card p-5">
          <h2 className="font-extrabold">Assigned queues</h2>
          <div className="mt-4 space-y-2">
            {queues.length === 0 && (
              <p className="text-sm text-slate-500">
                No queues assigned yet. Ask an organization admin to assign services to your account.
              </p>
            )}
            {queues.map((q) => (
              <button
                key={q.queue_id}
                onClick={() => setSelected(q.queue_id)}
                className={`w-full rounded-xl border p-3 text-left transition ${
                  selected === q.queue_id ? 'border-sky-400 bg-sky-50' : 'border-slate-200 hover:border-sky-200'
                }`}
              >
                <div className="font-bold">{q.service_name}</div>
                <div className="mt-1 text-xs text-slate-500">
                  Current: {q.current_token ?? '—'} · Waiting: {q.waiting ?? 0}
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="card p-5 lg:col-span-2">
          <h2 className="font-extrabold">Queue controls</h2>
          {current && (
            <p className="mt-2 text-sm text-slate-500">
              Selected: <strong>{current.service_name}</strong> · Current token:{' '}
              <strong>{current.current_token ?? 'none'}</strong> · Waiting: <strong>{current.waiting}</strong>
            </p>
          )}

          <div className="mt-5 flex flex-wrap gap-3">
            <button disabled={loading || !selected} onClick={callNext} className="btn btn-primary">
              Call next
            </button>
            <button
              disabled={loading || !activeToken}
              onClick={() => tokenAction('start', 'Start')}
              className="btn"
              style={{background: '#0ea5e9', color: '#fff'}}
            >
              Start
            </button>
            <button
              disabled={loading || !activeToken}
              onClick={() => tokenAction('complete', 'Complete')}
              className="btn"
              style={{background: '#10b981', color: '#fff'}}
            >
              Complete
            </button>
            <button
              disabled={loading || !activeToken}
              onClick={() => tokenAction('skip', 'Skip')}
              className="btn"
              style={{background: '#f59e0b', color: '#fff'}}
            >
              Skip
            </button>
            <button
              disabled={loading || !activeToken}
              onClick={() => tokenAction('recall', 'Recall')}
              className="btn btn-soft"
            >
              Recall
            </button>
          </div>

          <h3 className="mt-8 font-extrabold">Active token</h3>
          {activeToken ? (
            <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-2xl font-black">{activeToken.token_code}</p>
                  <p className="mt-1 text-sm text-slate-500">Token #{activeToken.token_number}</p>
                </div>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-bold uppercase tracking-wide text-slate-700 border border-slate-200">
                  {activeToken.status}
                </span>
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-400">
              Press <strong>Call next</strong> to pull the next waiting customer into an active token.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
