import React, { useState, useEffect } from 'react'
import { authApi } from '../api/client'
import { useStore } from '../store'
import toast from 'react-hot-toast'
import { BASE_URL } from '../api/client'

type Step = 'credentials' | 'mfa_code' | 'mfa_enroll'

export default function LoginPage() {
  const setUser = useStore(s => s.setUser)
  const [email, setEmail] = useState('')
  const [pw, setPw] = useState('')
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)

  // Multi-step login: most people just hit `credentials` and are done.
  // `mfa_code` / `mfa_enroll` only appear for accounts where MFA is
  // enabled or required (api/middleware/mfa.py enforces this for
  // admin/owner org roles) — see api/routes/auth.py's /login response
  // shapes for what drives these transitions.
  const [step, setStep] = useState<Step>('credentials')
  const [mfaCode, setMfaCode] = useState('')
  const [setupToken, setSetupToken] = useState('')
  const [mfaSecret, setMfaSecret] = useState('')
  const [mfaUri, setMfaUri] = useState('')

  // After Google OAuth callback, the URL will have ?google_token=...&refresh_token=...
  // Pick them up, store in localStorage, and log the user in automatically.
  // OAuth error redirects (?error=...) are handled by App.tsx before this
  // component mounts.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const googleToken = params.get('google_token')
    const refreshToken = params.get('refresh_token')
    if (googleToken) {
      localStorage.setItem('token', googleToken)
      if (refreshToken) {
        localStorage.setItem('refresh_token', refreshToken)
      }
      authApi.me().then(me => {
        setUser(me)
        toast.success('Signed in with Google!')
        window.history.replaceState({}, '', '/')
      }).catch(() => {
        toast.error('Google sign-in failed, please try again')
        localStorage.removeItem('token')
        localStorage.removeItem('refresh_token')
        window.history.replaceState({}, '', '/')
      })
    }
  }, [])

  const handleGoogleLogin = () => {
    setGoogleLoading(true)
    window.location.href = `${BASE_URL}/api/auth/google/login`
  }

  const finishLogin = async (welcomeMsg: string) => {
    const me = await authApi.me()
    setUser(me)
    toast.success(welcomeMsg)
  }

  const resetToCredentials = () => {
    setStep('credentials')
    setMfaCode('')
    setSetupToken('')
    setMfaSecret('')
    setMfaUri('')
  }

  const submitCredentials = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !pw) return
    setLoading(true)
    try {
      const data = mode === 'login' ? await authApi.login(email, pw) : await authApi.register(email, pw)

      if (data.mfa_code_required) {
        setStep('mfa_code')
        return
      }
      if (data.mfa_enrollment_required) {
        // This role requires MFA and hasn't enrolled yet — the login
        // response gives a narrow-scope setup_token (good ONLY for
        // /mfa/setup and /mfa/verify, not for anything else) rather than
        // a real session, so enrollment can't be skipped.
        setSetupToken(data.setup_token)
        const setup = await authApi.mfaSetup(data.setup_token)
        setMfaSecret(setup.secret)
        setMfaUri(setup.provisioning_uri)
        setStep('mfa_enroll')
        return
      }

      await finishLogin(mode === 'login' ? 'Welcome back!' : 'Account created!')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const submitMfaCode = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!mfaCode) return
    setLoading(true)
    try {
      const data = await authApi.login(email, pw, mfaCode)
      if (data.access_token) {
        await finishLogin('Welcome back!')
      } else {
        toast.error('Invalid code')
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Invalid or expired code')
      setMfaCode('')
    } finally {
      setLoading(false)
    }
  }

  const submitMfaEnroll = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!mfaCode) return
    setLoading(true)
    try {
      await authApi.mfaVerify(mfaCode, setupToken)
      await finishLogin('MFA enabled — welcome to AutoFlow!')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Invalid code — check your authenticator app and try again')
      setMfaCode('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg)' }}>
      <div style={{ position: 'fixed', inset: 0, backgroundImage: 'radial-gradient(var(--border) 1px, transparent 1px)', backgroundSize: '28px 28px', opacity: 0.4, pointerEvents: 'none' }} />

      <div style={{ position: 'relative', width: 380, background: 'var(--bg2)', border: '1px solid var(--border)', borderRadius: 14, padding: '36px 32px', boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }}>
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 32 }}>
          <div style={{ width: 36, height: 36, background: 'linear-gradient(135deg, var(--accent), #a855f7)', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(124,58,237,0.4)' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          </div>
          <div>
            <div style={{ fontWeight: 800, fontSize: 18, color: 'var(--text)', letterSpacing: '-0.02em' }}>AutoFlow</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: -1 }}>Workflow Automation</div>
          </div>
        </div>

        {step === 'credentials' && (
          <>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6, color: 'var(--text)' }}>
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </h2>
            <p style={{ color: 'var(--text3)', fontSize: 13, marginBottom: 24 }}>
              {mode === 'login' ? 'Welcome back to AutoFlow' : 'Start automating your workflows'}
            </p>

            <button
              onClick={handleGoogleLogin}
              disabled={googleLoading}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
                padding: '11px 0', background: '#fff', color: '#3c4043', border: '1px solid #dadce0',
                borderRadius: 8, fontWeight: 600, fontSize: 14,
                cursor: googleLoading ? 'not-allowed' : 'pointer', opacity: googleLoading ? 0.7 : 1,
                marginBottom: 16, transition: 'box-shadow 0.15s',
              }}
              onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 1px 6px rgba(0,0,0,0.2)')}
              onMouseLeave={e => (e.currentTarget.style.boxShadow = 'none')}
            >
              <svg width="18" height="18" viewBox="0 0 48 48">
                <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                <path fill="none" d="M0 0h48v48H0z"/>
              </svg>
              {googleLoading ? 'Redirecting…' : 'Continue with Google'}
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
              <span style={{ fontSize: 11, color: 'var(--text3)', fontWeight: 500 }}>OR</span>
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>

            <form onSubmit={submitCredentials} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>Email</label>
                <input type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required autoFocus />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>Password</label>
                <input type="password" placeholder="••••••••" value={pw} onChange={e => setPw(e.target.value)} required />
                {mode === 'register' && <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>Must be less than 72 characters</div>}
              </div>
              <button type="submit" disabled={loading || !email || !pw} style={{ marginTop: 8, padding: '11px 0', background: 'linear-gradient(135deg, var(--accent), #a855f7)', color: '#fff', borderRadius: 8, fontWeight: 700, fontSize: 14, opacity: loading ? 0.7 : 1, boxShadow: '0 4px 14px rgba(124,58,237,0.35)', transition: 'opacity 0.15s', cursor: loading ? 'not-allowed' : 'pointer' }}>
                {loading ? 'Please wait…' : mode === 'login' ? 'Sign in →' : 'Create account →'}
              </button>
            </form>

            <div style={{ marginTop: 20, textAlign: 'center', color: 'var(--text3)', fontSize: 13 }}>
              {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
              <button onClick={() => setMode(m => m === 'login' ? 'register' : 'login')} style={{ background: 'none', color: 'var(--accent)', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
                {mode === 'login' ? 'Register' : 'Sign in'}
              </button>
            </div>
          </>
        )}

        {step === 'mfa_code' && (
          <>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6, color: 'var(--text)' }}>Two-factor code</h2>
            <p style={{ color: 'var(--text3)', fontSize: 13, marginBottom: 24 }}>
              Enter the 6-digit code from your authenticator app.
            </p>
            <form onSubmit={submitMfaCode} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <input
                inputMode="numeric" autoFocus maxLength={6} placeholder="000000"
                value={mfaCode} onChange={e => setMfaCode(e.target.value.replace(/\D/g, ''))}
                style={{ textAlign: 'center', fontSize: 22, letterSpacing: '0.3em', fontFamily: 'var(--mono)', padding: '12px 0' }}
              />
              <button type="submit" disabled={loading || mfaCode.length !== 6} style={{ padding: '11px 0', background: 'linear-gradient(135deg, var(--accent), #a855f7)', color: '#fff', borderRadius: 8, fontWeight: 700, fontSize: 14, opacity: (loading || mfaCode.length !== 6) ? 0.6 : 1, cursor: (loading || mfaCode.length !== 6) ? 'not-allowed' : 'pointer' }}>
                {loading ? 'Verifying…' : 'Verify →'}
              </button>
            </form>
            <button onClick={resetToCredentials} style={{ marginTop: 16, background: 'none', color: 'var(--text3)', fontSize: 12, cursor: 'pointer', width: '100%', textAlign: 'center' }}>
              ← Back
            </button>
          </>
        )}

        {step === 'mfa_enroll' && (
          <>
            <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6, color: 'var(--text)' }}>Set up two-factor auth</h2>
            <p style={{ color: 'var(--text3)', fontSize: 13, marginBottom: 20, lineHeight: 1.5 }}>
              Your role in this organization requires MFA. Scan this with Google Authenticator, Authy, or 1Password, then enter the code it shows.
            </p>
            {mfaUri && (
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
                <img
                  alt="MFA setup QR code"
                  width={160} height={160}
                  style={{ borderRadius: 8, background: '#fff', padding: 8 }}
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(mfaUri)}`}
                />
              </div>
            )}
            {mfaSecret && (
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4 }}>Can't scan? Enter this key manually:</div>
                <code style={{ fontSize: 12, fontFamily: 'var(--mono)', background: 'var(--bg3)', padding: '4px 10px', borderRadius: 6, color: 'var(--text2)', letterSpacing: '0.05em' }}>{mfaSecret}</code>
              </div>
            )}
            <form onSubmit={submitMfaEnroll} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <input
                inputMode="numeric" autoFocus maxLength={6} placeholder="000000"
                value={mfaCode} onChange={e => setMfaCode(e.target.value.replace(/\D/g, ''))}
                style={{ textAlign: 'center', fontSize: 22, letterSpacing: '0.3em', fontFamily: 'var(--mono)', padding: '12px 0' }}
              />
              <button type="submit" disabled={loading || mfaCode.length !== 6} style={{ padding: '11px 0', background: 'linear-gradient(135deg, var(--accent), #a855f7)', color: '#fff', borderRadius: 8, fontWeight: 700, fontSize: 14, opacity: (loading || mfaCode.length !== 6) ? 0.6 : 1, cursor: (loading || mfaCode.length !== 6) ? 'not-allowed' : 'pointer' }}>
                {loading ? 'Verifying…' : 'Enable & Sign In →'}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
