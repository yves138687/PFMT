export interface LoginRequest {
  username: string
  password: string
}

export interface UserProfile {
  user_id: string
  username: string
  display_name: string
  status: 'active' | 'disabled'
  last_login_at?: string | null
}

export interface LoginResponse {
  access_token: string
  token_type?: 'bearer' | string
  expires_at?: string
  user: UserProfile
}
