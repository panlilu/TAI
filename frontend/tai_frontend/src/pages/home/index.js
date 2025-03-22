import React from 'react';
import './style.css';

export default function HomePage() {
  return (
    <div className="home-container">
      <header className="hero-section">
        <h1 className="hero-title animate__animated animate__fadeInDown">
          TAI AI文章管理平台
        </h1>
        <p className="hero-subtitle animate__animated animate__fadeInUp">
          集成AI驱动的文章分析、智能审稿和文章管理
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
          <h3>智能文章分析</h3>
          <p>深度语义解析，自动生成结构化数据</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🔍</div>
          <h3>AI辅助审稿</h3>
          <p>基于大模型的评审建议，支持多种模型可供选择</p>
        </div>
        <div className="feature-card">
          <div className="feature-icon">🔧</div>
          <h3>自定义扩展需求</h3>
          <p>多种参数可自定义，满足不同需求</p>
        </div>
      </section>
    </div>
  );
}