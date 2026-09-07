---
layout: page
---

<script setup>
import Hero from './.vitepress/theme/components/Hero.vue'
import Features from './.vitepress/theme/components/Features.vue'
import HowItWorks from './.vitepress/theme/components/HowItWorks.vue'
import UseCases from './.vitepress/theme/components/UseCases.vue'
import Pricing from './.vitepress/theme/components/Pricing.vue'
import Footer from './.vitepress/theme/components/Footer.vue'
import { getHomeEnContent } from './.vitepress/theme/data/home-en.js'

const { heroData, featuresData, howItWorksData, useCasesData, pricingData, footerData } = getHomeEnContent()
</script>

<Hero v-bind="heroData" />
<Features v-bind="featuresData" />
<HowItWorks v-bind="howItWorksData" />
<UseCases v-bind="useCasesData" />
<Pricing v-bind="pricingData" />
<Footer v-bind="footerData" />
