<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/authStore'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  password: ''
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function submitLogin() {
  const valid = await formRef.value?.validate()
  if (!valid) {
    return
  }

  await authStore.login(form)
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/dashboard'
  await router.push(redirect)
}
</script>

<template>
  <main class="login-view">
    <section class="login-view__panel">
      <div class="login-view__intro">
        <span class="login-view__logo">PF</span>
        <h1>PFMT</h1>
        <p>个人文件管理工具</p>
      </div>

      <el-form ref="formRef" class="login-view__form" :model="form" :rules="rules" label-position="top">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" size="large">
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            show-password
            size="large"
            @keyup.enter="submitLogin"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-button class="login-view__submit" type="primary" size="large" :loading="authStore.loading" @click="submitLogin">
          登录
        </el-button>
      </el-form>

      <footer>v0.1.0</footer>
    </section>
  </main>
</template>

<style scoped>
.login-view {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(180deg, rgb(246 248 251 / 95%), rgb(238 243 250 / 95%)),
    #f6f8fb;
}

.login-view__panel {
  width: min(100%, 420px);
  padding: 34px;
  background: var(--pfmt-surface);
  border: 1px solid var(--pfmt-border-soft);
  border-radius: 8px;
  box-shadow: 0 20px 60px rgb(15 23 42 / 10%);
}

.login-view__intro {
  margin-bottom: 24px;
}

.login-view__logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  margin-bottom: 16px;
  border-radius: 8px;
  color: #ffffff;
  background: var(--pfmt-primary);
  font-weight: 700;
}

.login-view h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
}

.login-view p {
  margin: 8px 0 0;
  color: var(--pfmt-text-muted);
}

.login-view__form {
  display: grid;
  gap: 2px;
}

.login-view__submit {
  width: 100%;
  margin-top: 8px;
}

.login-view footer {
  margin-top: 22px;
  color: var(--pfmt-text-muted);
  font-size: 12px;
  text-align: center;
}
</style>
