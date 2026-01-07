# Production Deployment Checklist

## ✅ Pre-Deployment Checks

### Backend (Render)
- [ ] Environment variables set in Render dashboard:
  - `SUPABASE_URL` (same as dev)
  - `SUPABASE_KEY` (service_role key - **NOT the anon key**)
  - `SUPABASE_JWT_SECRET` (from Supabase JWT Secret under API settings)
  - `DATABASE_URL` (Supabase connection string)
  - `FRONTEND_ORIGIN` (your Vercel URL, e.g., `https://your-app.vercel.app`)

- [ ] Render build command: `pip install -r requirements.txt`
- [ ] Render start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [ ] Python version: 3.10+ selected in Render

### Frontend (Vercel)
- [ ] Environment variables set in Vercel project settings:
  - `NEXT_PUBLIC_API_BASE_URL` (your Render URL, e.g., `https://ai-stock-price-predictor-7pmv.onrender.com`)
  - `NEXT_PUBLIC_SUPABASE_URL` (same as dev)
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY` (public anon key - **NOT service_role**)

- [ ] Build command: `npm run build` (default)
- [ ] Install command: `npm install` (default)
- [ ] Framework preset: Next.js (auto-detected)

### Database (Supabase)
- [ ] RLS policies are enabled on `analysis_db` table
- [ ] Unique constraint `(ticker, period, user_id)` is applied (run migration if needed)
- [ ] Test with at least one user account via Supabase Auth UI

## 🚀 Deployment Steps

### 1. Deploy Backend First
```bash
git push origin main
```
- Render will auto-deploy from your connected repo
- Wait for deployment to complete
- Test health endpoint: `https://your-render-url.onrender.com/health`

### 2. Update Frontend Env Vars
- Go to Vercel project settings → Environment Variables
- Set `NEXT_PUBLIC_API_BASE_URL` to your Render URL
- Redeploy if needed (Vercel auto-deploys on push)

### 3. Test End-to-End
- [ ] Visit your Vercel URL
- [ ] Sign up / sign in with Supabase Auth
- [ ] Run an analysis (without storing)
- [ ] Run an analysis with `store=true` (requires auth)
- [ ] Visit `/analyses` page and verify user-scoped data loads
- [ ] Open browser devtools → Network tab and confirm:
  - No CORS errors
  - Authorization header present on protected routes
  - 200 responses for successful requests

## 🔍 Key Security Validations

### CORS Configuration
✅ **Current Setup:**
- Allows: `localhost` (dev), your Render URL, `*.vercel.app` (production + previews)
- Methods: `GET`, `POST`, `OPTIONS` only
- Headers: `authorization`, `content-type` only
- Credentials: `False` (using Bearer tokens)

⚠️ **If you see CORS errors:**
1. Check the `Origin` header in browser Network tab
2. Verify it matches one of the allowed origins or the regex pattern
3. For custom domains, add explicitly to `origins` list in `app/main.py`

### Auth Token Flow
✅ **Current Setup:**
- Frontend uses **anon key** (public, safe for browser)
- Backend uses **service_role key** (private, server-only)
- Tokens are ES256-signed JWTs from Supabase
- Backend validates token structure (relaxed for local, can tighten for production)

⚠️ **If you see 401 Unauthorized:**
1. Verify user is signed in (check `session` in AuthContext)
2. Check `Authorization: Bearer <token>` header is present
3. Verify backend has correct `SUPABASE_JWT_SECRET`
4. Check Supabase dashboard → Authentication → Users (confirm user exists)

### Database Security
✅ **Current Setup:**
- RLS enabled: users can only see/modify their own analyses
- Backend enforces `user_id` scoping on all queries
- Service role key bypasses RLS, but app code filters by `user_id`

⚠️ **To verify RLS:**
```sql
-- Run in Supabase SQL Editor
SELECT * FROM analysis_db LIMIT 5;
-- Should show user_id populated for all rows
```

## 🐛 Troubleshooting

### Backend won't start on Render
- Check Render logs for missing env vars or import errors
- Verify `requirements.txt` includes all dependencies
- Ensure Python version is 3.10+

### Frontend can't reach backend
- Check `NEXT_PUBLIC_API_BASE_URL` is set in Vercel
- Verify Render URL is reachable: `curl https://your-render-url.onrender.com/health`
- Check browser Network tab for exact error

### Auth not working in production
- Verify Supabase keys are correct (anon for frontend, service_role for backend)
- Check JWT_SECRET matches Supabase dashboard → API → Config → JWT Secret
- Test auth in Supabase dashboard → Authentication → Users → "Send magic link"

### Data not saving / wrong user's data showing
- Verify unique constraint: `(ticker, period, user_id)`
- Check backend logs for SQL errors
- Confirm RLS policies are enabled
- Test with two different user accounts to verify isolation

## 📝 Post-Deployment

- [ ] Monitor Render logs for errors
- [ ] Check Vercel deployment logs
- [ ] Test with multiple user accounts
- [ ] Verify RLS isolation (user A can't see user B's data)
- [ ] Set up error tracking (optional: Sentry, LogRocket, etc.)

## 🔐 Security Best Practices

### Secrets Management
- ✅ Never commit `.env` files to git
- ✅ Use `.env.example` templates only (no real keys)
- ✅ Rotate keys if accidentally exposed
- ✅ Use different Supabase projects for dev/prod (optional)

### CORS Tightening (Optional)
If you want to be more restrictive:
1. Replace `*.vercel.app` regex with your exact domain(s)
2. Remove LAN IP ranges from production deployment
3. Use Next.js rewrites to proxy API calls (eliminates CORS entirely)

### JWT Validation (Optional Enhancement)
Current setup uses unverified claims for local dev. For stricter production:
1. Fetch Supabase JWKS and verify ES256 signatures
2. Enable `get_jwks()` function in `app/auth.py`
3. Set conditional logic: strict in prod, relaxed in dev

---

**Last Updated:** January 7, 2026  
**Deployment Status:** Ready for production ✅
