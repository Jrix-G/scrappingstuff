import { createClient } from '@supabase/supabase-js';

const supabaseUrl  = process.env.REACT_APP_SUPABASE_URL  ?? '';
const supabaseAnon = process.env.REACT_APP_SUPABASE_ANON_KEY ?? '';

if (!supabaseUrl || !supabaseAnon) {
  console.warn('[Tandor] REACT_APP_SUPABASE_URL ou REACT_APP_SUPABASE_ANON_KEY manquant — auth désactivée.');
}

export const supabase = createClient(supabaseUrl, supabaseAnon);
