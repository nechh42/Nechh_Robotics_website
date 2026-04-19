// assets/js/supabase-config.js
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm'

// SUPABASE CONFIG - DOÐRUSU BURASI
const supabaseUrl = 'https://beuajrnifarxewnwsmml.supabase.co'
const supabaseAnonKey = 'sb_publishable_KmPrgSIUNtd-XwgJ6MsYAQ_CjtqA9gX'

// Client oluþtur
const supabase = createClient(supabaseUrl, supabaseAnonKey)

export { supabase }
