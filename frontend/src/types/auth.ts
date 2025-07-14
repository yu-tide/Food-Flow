export type SendCodeRequest = {
  phone: string
  scene: 'register'
}

export type RegisterRequest = {
  phone: string
  code: string
  nickname: string
  password: string
}

export type LoginRequest = {
  phone: string
  password: string
}

export type AuthUser = {
  id: string
  phone: string
  nickname: string
  avatarText: string
}

export type LoginResponse = {
  access_token: string
  token_type: string
  user: AuthUser
}
