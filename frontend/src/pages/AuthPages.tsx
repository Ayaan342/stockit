import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../context/useAuth'

export function LoginPage() {
  const { login } = useAuth(); const navigate = useNavigate(); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [loading, setLoading] = useState(false)
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(''); setLoading(true); try { await login(email, password); navigate('/dashboard') } catch (err) { setError(err instanceof ApiError ? err.message : 'Unable to sign in.') } finally { setLoading(false) } }
  return <AuthFrame title="Welcome back" subtitle="Sign in to your portfolio tracker."><form onSubmit={submit}><label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Password<input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>{error && <p className="form-error">{error}</p>}<button className="primary" disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button><p className="auth-switch">New to StockIt? <Link to="/register">Create an account</Link></p></form></AuthFrame>
}

export function RegisterPage() {
  const { register } = useAuth(); const navigate = useNavigate(); const [name, setName] = useState(''); const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [success, setSuccess] = useState(''); const [loading, setLoading] = useState(false)
  const submit = async (event: FormEvent) => { event.preventDefault(); if (password.length < 8) return setError('Password must contain at least 8 characters.'); setError(''); setLoading(true); try { await register(name, email, password); setSuccess('Account created. You can now sign in.'); setTimeout(() => navigate('/login'), 700) } catch (err) { setError(err instanceof ApiError ? err.message : 'Unable to create account.') } finally { setLoading(false) } }
  return <AuthFrame title="Track your investments" subtitle="Record your portfolio and follow current market values."><form onSubmit={submit}><label>Name<input required value={name} onChange={(e) => setName(e.target.value)} /></label><label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label><label>Password<input type="password" minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} /></label>{error && <p className="form-error">{error}</p>}{success && <p className="form-success">{success}</p>}<button className="primary" disabled={loading}>{loading ? 'Creating account…' : 'Create account'}</button><p className="auth-switch">Already registered? <Link to="/login">Sign in</Link></p></form></AuthFrame>
}

function AuthFrame({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) { return <main className="auth-page"><section className="auth-panel"><Link className="brand" to="/login"><span>◆</span> StockIt</Link><p className="eyebrow">Portfolio tracker</p><h1>{title}</h1><p className="muted">{subtitle}</p>{children}</section></main> }
