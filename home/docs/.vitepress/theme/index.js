import DefaultTheme from 'vitepress/theme'
import './styles/custom.css'
import Hero from './components/Hero.vue'
import Carousel from './components/Carousel.vue'
import Features from './components/Features.vue'
import HowItWorks from './components/HowItWorks.vue'
import UseCases from './components/UseCases.vue'
import Pricing from './components/Pricing.vue'
import PricingComparison from './components/PricingComparison.vue'
import Footer from './components/Footer.vue'
import MobileNav from './components/MobileNav.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'
import Layout from './Layout.vue'
import NotFound from './NotFound.vue'

export default {
  extends: DefaultTheme,
  Layout,
  NotFound,
  enhanceApp({ app }) {
    app.component('Hero', Hero)
    app.component('Carousel', Carousel)
    app.component('Features', Features)
    app.component('HowItWorks', HowItWorks)
    app.component('UseCases', UseCases)
    app.component('Pricing', Pricing)
    app.component('PricingComparison', PricingComparison)
    app.component('Footer', Footer)
    app.component('MobileNav', MobileNav)
    app.component('LanguageSwitcher', LanguageSwitcher)
  }
}
