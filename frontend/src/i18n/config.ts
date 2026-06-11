import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  en: {
    translation: {
      appName: 'Stock Trading System',
      nav: {
        home: 'Home',
        data: 'Data Collection',
        portfolio: 'Portfolio',
        screening: 'Screening',
        simulation: 'Simulation',
        results: 'Results',
        stocks: 'Stock Analysis',
        forecast: 'Forecast',
        jobs: 'Jobs',
      },
      auth: {
        login: 'Log in',
        register: 'Register',
        logout: 'Log out',
        password: 'Password',
        username: 'Username',
      },
    },
  },
  'zh-CN': {
    translation: {
      appName: '股票交易系统',
      nav: {
        home: '首页',
        data: '数据收集',
        portfolio: '投资组合',
        screening: '选股筛选',
        simulation: '回测',
        results: '结果分析',
        stocks: '股票分析',
        forecast: '预测分析',
        jobs: '任务',
      },
      auth: {
        login: '登录',
        register: '注册',
        logout: '退出',
        password: '密码',
        username: '用户名',
      },
    },
  },
};

i18n.use(initReactI18next).init({
  resources,
  lng: 'zh-CN',
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
