<script setup>
import { RouterLink } from 'vue-router'
</script>

<template>
  <div class="text-center py-5">
    <div style="font-size: 4rem">🧭</div>
    <h1 class="h4">Off the trail!</h1>
    <p class="text-muted">The page you are looking for does not exist.</p>
    <RouterLink to="/" class="btn btn-success">Back to dashboard</RouterLink>
  </div>
</template>

