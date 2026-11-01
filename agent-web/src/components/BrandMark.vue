<script setup>
import logo from '../assets/rhizome-logo.png'
defineProps({ label: { type: String, default: 'Rhizome' } })
</script>

<template>
  <svg class="brand-mark" viewBox="290 327 675 432" role="img" :aria-label="label">
    <image :href="logo" width="1254" height="1254" />
  </svg>
</template>
