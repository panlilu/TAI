import React from 'react';
import './style.css';

export default function HomePage() {
  return (
    <div className="home-container">
      <header className="hero-section">
        <h1 className="hero-title animate__animated animate__fadeInDown">
          TAI 智能学术协作平台
        </h1>
        <p className="hero-subtitle animate__animated animate__fadeInUp">
          下一代科研协作工具，集成AI驱动的论文分析、智能审稿和学术资源管理
        </p>
        <div className="cta-buttons">
          <a href="/login" className="cta-button primary">立即开始</a>
          <a href="#features" className="cta-button secondary" onClick={(e) => {
            e.preventDefault();
            document.getElementById('features').scrollIntoView({ behavior: 'smooth' });
          }}>功能特性</a>
        </div>
      </header>

      <section className="features-section" id="features">
        <div className="feature-card">
          <div className="feature-icon">📘</div>
          <h3>智能论文分析</h3>
          <p>深度语义解析，自动生成结构化摘要，快速定位核心贡献</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🔍</div>
          <h3>AI辅助审稿</h3>
          <p>基于大模型的评审建议，支持格式检查与学术规范验证</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🤝</div>
          <h3>协作工作流</h3>
          <p>多角色协同评审，版本对比，实时批注与讨论</p>
        </div>
      </section>
    </div>
  );
}