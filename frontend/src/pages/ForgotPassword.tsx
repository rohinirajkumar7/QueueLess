import {useState} from 'react';
import type {FormEvent} from 'react';
import {Link} from 'react-router-dom';
import {api, apiError} from '../services/api';

export default function ForgotPassword() {
  const [email, setEmail] = useState('customer@queueless.example.com');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);
    try {
      const r = await api.post('/auth/forgot-password', {email});
      setMessage(r.data.message || 'If an account exists, a reset link was sent.');
    } catch (err) {
      setError(apiError(err, 'Unable to request password reset.'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-wrap py-14">
      <div className="mx-auto max-w-lg card p-8 sm:p-10">
        <p className="text-sm font-bold uppercase tracking-[.16em] text-indigo-600">Account recovery</p>
        <h1 className="mt-2 text-3xl font-black">Forgot password?</h1>
        <p className="mt-3 text-slate-500">Enter your email and we will send a single-use reset link to your inbox.</p>
        <form onSubmit={submit} className="mt-7 space-y-5">
          <div>
            <label className="label">Email address</label>
            <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          {message && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-700">{message}</div>}
          {error && <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm font-semibold text-rose-700">{error}</div>}
          <button disabled={loading} className="btn btn-primary w-full">{loading ? 'Sending...' : 'Send reset link'}</button>
        </form>
        <Link to="/login" className="mt-6 block text-center text-sm font-bold text-indigo-600">Back to sign in</Link>
      </div>
    </div>
  );
}
