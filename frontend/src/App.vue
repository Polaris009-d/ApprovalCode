<template>
  <div id="approval-app">
    <!-- 顶部栏 -->
    <header class="topbar">
      <div class="topbar-left">
        <span class="logo">A</span>
        <span class="app-name">AI 审批中心</span>
      </div>
      <div class="topbar-right">
        <span class="topbar-status">
          <span class="dot online"></span> 系统正常 · Agent 在线
        </span>
        <span class="topbar-user">管理员</span>
      </div>
    </header>

    <div class="app-body">
      <!-- 左侧导航 -->
      <nav class="sidebar">
        <router-link to="/" class="nav-item" exact-active-class="active">
          <span class="nav-icon">&#9703;</span> 工作台
        </router-link>
        <router-link to="/review" class="nav-item" active-class="active">
          <span class="nav-icon">&#9776;</span> 智能审查
        </router-link>
        <router-link to="/pending" class="nav-item" active-class="active">
          <span class="nav-icon">&#9776;</span> 待审批
        </router-link>
        <router-link to="/history" class="nav-item" active-class="active">
          <span class="nav-icon">&#9776;</span> 审查记录
        </router-link>
        <router-link to="/legal-kb" class="nav-item" active-class="active">
          <span class="nav-icon">&#167;</span> 法律知识库
        </router-link>
        <router-link to="/agents" class="nav-item" active-class="active">
          <span class="nav-icon">&#9881;</span> Agent 监控
        </router-link>
      </nav>

      <!-- 主内容区 -->
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script>
export default { name: 'App' }
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f1f5f9; color: #1e293b; }
#approval-app { min-height: 100vh; display: flex; flex-direction: column; }
.topbar { display: flex; justify-content: space-between; align-items: center; height: 52px; padding: 0 20px; background: #fff; border-bottom: 1px solid #e2e8f0; flex-shrink: 0; }
.topbar-left { display: flex; align-items: center; gap: 8px; }
.logo { width: 28px; height: 28px; background: #3b82f6; color: #fff; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 800; }
.app-name { font-size: 1.05rem; font-weight: 700; color: #1e293b; }
.topbar-right { display: flex; align-items: center; gap: 20px; }
.topbar-status { font-size: 0.8rem; color: #16a34a; display: flex; align-items: center; gap: 6px; }
.dot { width: 7px; height: 7px; border-radius: 50%; }
.dot.online { background: #22c55e; box-shadow: 0 0 5px #22c55e; }
.topbar-user { font-size: 0.85rem; color: #64748b; }
.app-body { display: flex; flex: 1; }
.sidebar { width: 200px; background: #fff; border-right: 1px solid #e2e8f0; padding: 12px 0; flex-shrink: 0; display: flex; flex-direction: column; gap: 2px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 10px 20px; font-size: 0.9rem; color: #475569; text-decoration: none; transition: all 0.15s; border-left: 3px solid transparent; }
.nav-item:hover { background: #f8fafc; color: #1e293b; }
.nav-item.active { background: #eff6ff; color: #2563eb; border-left-color: #3b82f6; font-weight: 600; }
.nav-icon { font-size: 0.9rem; width: 22px; text-align: center; color: #64748b; }
.nav-item.active .nav-icon { color: #3b82f6; }
.main-content { flex: 1; padding: 20px 24px; overflow-y: auto; min-width: 0; }
.page-title { font-size: 1.3rem; font-weight: 700; color: #1e293b; margin-bottom: 20px; }
</style>
