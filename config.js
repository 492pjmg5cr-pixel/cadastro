// Configurações do app. Edite antes de publicar.
window.APP_CONFIG = {
  // Hashes SHA-256 de "usuario:senha" (usuário em minúsculas). Pode ter vários logins de administrador.
  // Gere o seu abrindo gerar-senha.html. TROQUE por senhas fortes antes de usar de verdade.
  ADM_HASH: [
    '88bdb45f4440fb862975c73487c92ff13659294b7d118d94ae331bea5ee57f20', // adm / admin
    '506811c8bcaa44fb8e3653fe8b26567d7231d4c7b060bfa668e6b89dfa5ba935'  // adm / 123456
  ],
  // Modelo usado no flyer com IA (só vale se você informar uma chave de API no app).
  AI_MODEL: 'claude-sonnet-5-5',
  // Banco de dados Supabase (Project Settings > API). Deixe vazio para usar só o navegador.
  SUPABASE_URL: '',   // ex.: 'https://abcdefgh.supabase.co'
  SUPABASE_KEY: ''    // chave "anon public"
};
