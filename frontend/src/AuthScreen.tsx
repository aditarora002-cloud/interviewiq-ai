import { useState } from 'react';
import { BrainCircuit, ShieldCheck, LoaderCircle, LogIn } from 'lucide-react';
import { postJSON, setAuthToken } from './api';

export interface Account { id: string; name: string; email: string; }

export default function AuthScreen({onLogin}: {onLogin: (user:Account)=>void}) {
  const [mode,setMode] = useState<'login'|'register'>('login');
  const [email,setEmail] = useState('');
  const [password,setPassword] = useState('');
  const [name,setName] = useState('');
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  async function submit(e:React.FormEvent) {
    e.preventDefault(); setBusy(true); setError('');
    try {
      const result = await postJSON(`/api/auth/${mode}`, mode === 'register' ? {name,email,password} : {email,password});
      setAuthToken(result.token);
      onLogin(result.user);
    } catch (exc) { setError(exc instanceof Error ? exc.message : 'Unable to sign in.'); }
    finally { setBusy(false); }
  }
  return <div className="auth-page">
    <div className="auth-panel">
      <div className="auth-brand"><span className="auth-mark"><BrainCircuit size={27}/></span><div><strong>InterviewIQ</strong><small>YOUR PERSONAL CAREER STUDIO</small></div></div>
      <div className="eyebrow">PRIVATE PRACTICE WORKSPACE</div>
      <h1>{mode === 'login' ? 'Welcome back.' : 'Create your workspace.'}</h1>
      <p className="auth-lead">Sign in to save your interviews, resume analyses, job matches, and progress under your account.</p>
      <div className="auth-switch" role="tablist" aria-label="Account access">
        <button type="button" role="tab" aria-selected={mode==='login'} className={mode==='login'?'active':''} onClick={()=>{setMode('login');setError('')}}>Sign in</button>
        <button type="button" role="tab" aria-selected={mode==='register'} className={mode==='register'?'active':''} onClick={()=>{setMode('register');setError('')}}>Create account</button>
      </div>
      <form className="auth-form" onSubmit={submit}>
        {mode==='register'&&<><label htmlFor="auth-name">Your name</label><input id="auth-name" required minLength={2} maxLength={80} autoComplete="name" placeholder="Your name" value={name} onChange={e=>setName(e.target.value)}/></>}
        <label htmlFor="auth-email">Email address</label><input id="auth-email" required type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={e=>setEmail(e.target.value)}/>
        <label htmlFor="auth-password">Password</label><input id="auth-password" required minLength={mode==='register'?8:1} type="password" autoComplete={mode==='login'?'current-password':'new-password'} placeholder={mode==='register'?'At least 8 characters':'Your password'} value={password} onChange={e=>setPassword(e.target.value)}/>
        {error && <div className="auth-error" role="alert">{error}</div>}
        <button className="btn primary auth-submit" disabled={busy} type="submit">{busy?<LoaderCircle className="spin" size={17}/>:<LogIn size={17}/>} {mode==='login'?'Sign in':'Create my account'}</button>
      </form>
      <div className="auth-foot"><ShieldCheck size={16}/><span>Passwords are hashed on the server. Your records are only accessible when signed in. Use HTTPS when deployed.</span></div>
    </div>
    <div className="auth-art"><div className="auth-art-inner"><span>INTERVIEWIQ / STUDIO</span><h2>Prepare with purpose.<br/>Improve with evidence.</h2><p>One place for AI interview practice, live camera coaching, researched job targeting and a history of your progress.</p><div className="auth-art-orbit"><BrainCircuit size={96}/></div></div></div>
  </div>;
}
