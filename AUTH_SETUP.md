# Multi-User Authentication Setup Guide

## Overview
This implementation adds Supabase Auth with row-level security (RLS) to ensure each user only sees their own analyses.

---

## Backend Setup

### 1. Environment Variables

Add to your `.env` file (backend root):

```env
# Existing vars
SUPABASE_URL=https://oxeawaivdvnquzrasubj.supabase.co
SUPABASE_KEY=your-service-role-key-here

# NEW: Add JWT secret for token validation
SUPABASE_JWT_SECRET=your-jwt-secret-here
```

**Where to find JWT_SECRET:**
1. Go to Supabase Dashboard → Project Settings → API
2. Scroll to "JWT Settings"
3. Copy the "JWT Secret" value

### 2. Dependencies
Already installed:
- `python-jose[cryptography]` - JWT validation

### 3. Database Schema Updates

You've already run these in Supabase SQL Editor:

```sql
-- Add user_id column
alter table public.analysis_db
add column if not exists user_id uuid;

-- Index for performance
create index if not exists analyses_user_id_idx
on public.analysis_db (user_id);

-- Update unique constraint (IMPORTANT!)
-- Drop old constraint
alter table public.analysis_db 
drop constraint if exists analysis_db_ticker_period_key;

-- Add new constraint with user_id
alter table public.analysis_db
add constraint analysis_db_ticker_period_user_id_key
unique (ticker, period, user_id);

-- Enable RLS
alter table public.analysis_db enable row level security;

-- RLS Policies
create policy "analyses_select_own"
on public.analysis_db for select
using (user_id = auth.uid());

create policy "analyses_insert_own"
on public.analysis_db for insert
with check (user_id = auth.uid());

create policy "analyses_update_own"
on public.analysis_db for update
using (user_id = auth.uid())
with check (user_id = auth.uid());

create policy "analyses_delete_own"
on public.analysis_db for delete
using (user_id = auth.uid());
```

**CRITICAL:** Update the unique constraint to include `user_id` so multiple users can have analyses for the same ticker/period.

---

## Frontend Setup

### 1. Environment Variables

Create `web/.env.development.local` for local dev:

```env
# Backend API
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# Supabase (get from Dashboard → Project Settings → API)
NEXT_PUBLIC_SUPABASE_URL=https://oxeawaivdvnquzrasubj.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-public-key-here
```

**Where to find ANON_KEY:**
1. Supabase Dashboard → Project Settings → API
2. Copy "Project API keys" → "anon" → "public"

### 2. Production Environment Variables (Vercel)

In your Vercel dashboard, add:
- `NEXT_PUBLIC_API_BASE_URL` = your Render API URL
- `NEXT_PUBLIC_SUPABASE_URL` = your Supabase URL  
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` = your anon key

### 3. Dependencies
Already installed:
- `@supabase/supabase-js` - Supabase client for auth

---

## Testing Guide

### 1. Start Services

Terminal 1 - Backend:
```bash
cd C:\Users\taile\source\repos\ai_stock_price_predictor
uvicorn app.main:app --reload
```

Terminal 2 - Frontend:
```bash
cd web
npm run dev
```

### 2. Test Authentication Flow

1. **Sign Up:**
   - Visit http://localhost:3000/auth
   - Enter email and password (min 6 chars)
   - Click "Sign Up"
   - Check email for confirmation link
   - Click confirmation link

2. **Sign In:**
   - Return to http://localhost:3000/auth
   - Enter same email/password
   - Click "Sign In"
   - Should redirect to /analyses

3. **Test Protected Endpoints:**
   - Go to http://localhost:3000/analyses
   - Try "Run Analysis & Store" - should work
   - Try "Fetch Recent" - should only show YOUR analyses
   - Sign out and try again - should redirect to /auth

### 3. Test Multi-User Isolation

1. Create two users (different emails)
2. Sign in as User A:
   - Run analysis for AAPL/1y and store
   - Note the analysis appears
3. Sign out, sign in as User B:
   - Fetch analyses for AAPL - should be EMPTY
   - Run analysis for AAPL/1y and store
   - Should see only User B's analysis
4. Sign out, sign in as User A:
   - Should still see only User A's original analysis

### 4. Test API Directly (Optional)

Get a token:
```bash
# Sign in via Supabase returns access_token
# Or grab from browser devtools: Application → Local Storage → supabase.auth.token
```

Test authenticated endpoint:
```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     "http://localhost:8000/api/analyses?ticker=AAPL&limit=5"
```

Test unauthenticated (should fail):
```bash
curl "http://localhost:8000/api/analyses?ticker=AAPL&limit=5"
# Should return 401 Unauthorized
```

---

## Architecture Overview

### Authentication Flow

```
Frontend (Next.js)
    ↓
1. User signs in via Supabase Auth
    ↓
2. Supabase returns access_token (JWT)
    ↓
3. Frontend stores token in localStorage (automatic)
    ↓
4. API calls include: Authorization: Bearer <token>
    ↓
Backend (FastAPI)
    ↓
5. app/auth.py validates JWT with SUPABASE_JWT_SECRET
    ↓
6. Extracts user_id from JWT 'sub' claim
    ↓
7. Passes user_id to repository layer
    ↓
8. DB queries filter by user_id
```

### Files Created/Modified

**Backend:**
- `app/auth.py` - JWT validation and user extraction
- `app/main.py` - Added auth dependencies to endpoints
- `src/db/analysis_repo.py` - Added user_id filtering

**Frontend:**
- `web/lib/supabase.js` - Supabase client
- `web/contexts/AuthContext.jsx` - Auth state management
- `web/app/auth/page.jsx` - Sign in/up form
- `web/app/auth/auth.module.css` - Auth UI styles
- `web/app/layout.tsx` - Wrap app with AuthProvider
- `web/app/analyses/page.jsx` - Require auth, pass tokens
- `web/lib/api.js` - Add Authorization headers

---

## Security Notes

1. **Service Role Key:** 
   - Still used in backend for database operations
   - Never expose to frontend
   - Stored in backend `.env` only

2. **JWT Secret:**
   - Used to verify tokens are signed by Supabase
   - Never expose to frontend
   - Same secret from Supabase dashboard

3. **Anon Key:**
   - Public key, safe to expose in frontend
   - Used only for auth operations
   - Has limited permissions

4. **RLS Policies:**
   - Even with service role key, enforce user_id checks in code
   - RLS is backup layer when using anon key
   - Both layers = defense in depth

---

## Troubleshooting

### "Authentication required to store analyses"
- User not signed in
- Token expired (refresh page)
- Check browser console for auth state

### "Invalid authentication token"
- JWT_SECRET mismatch
- Token expired
- Wrong environment (dev token → prod backend)

### "Unique constraint violation"
- Old constraint without user_id
- Run the constraint update SQL above

### Empty analyses list
- Working as intended! Users are isolated
- Each user only sees their own data
- Check user_id in database to confirm

---

## Production Deployment

### Render (Backend):
Add environment variable:
```
SUPABASE_JWT_SECRET=your-jwt-secret-here
```

### Vercel (Frontend):
Add environment variables:
```
NEXT_PUBLIC_API_BASE_URL=https://your-api.onrender.com
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

### Supabase:
- Email confirmation is enabled by default
- Configure email templates: Authentication → Email Templates
- Set up custom SMTP (optional): Project Settings → Auth → SMTP Settings

---

## Next Steps (Optional Enhancements)

1. **Password Reset:** Use Supabase `resetPasswordForEmail()`
2. **OAuth:** Add Google/GitHub sign-in via Supabase Auth
3. **User Profiles:** Create `profiles` table with additional user data
4. **Rate Limiting:** Add per-user rate limits
5. **Admin Dashboard:** Create admin role to view all analyses
