import React, { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion, useInView } from 'motion/react'
import { useTheme } from '../ThemeProvider'

interface HeroVideoProps {
  className?: string
}

export const HeroVideo: React.FC<HeroVideoProps> = ({ className = '' }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const [canPlay, setCanPlay] = useState(false)
  const [mounted, setMounted] = useState(false)
  const reducedMotion = useReducedMotion()
  const isInView = useInView(containerRef, { amount: 0.1 })
  const { resolvedTheme } = useTheme()

  const isDark = resolvedTheme === 'dark'

  // Reset playback readiness on theme change so poster transitions gracefully
  useEffect(() => {
    setCanPlay(false)
  }, [isDark])

  // Mount video on client if reduced motion is disabled
  useEffect(() => {
    if (reducedMotion) return
    setMounted(true)
  }, [reducedMotion])

  // If already buffered, mark as ready immediately
  useEffect(() => {
    if (videoRef.current && videoRef.current.readyState >= 2) {
      setCanPlay(true)
    }
  }, [mounted, isDark])

  // Play/pause based on viewport visibility to conserve CPU/GPU
  useEffect(() => {
    if (!videoRef.current || reducedMotion) return
    if (isInView && document.visibilityState === 'visible') {
      videoRef.current.play().catch(() => {})
    } else {
      videoRef.current.pause()
    }
  }, [isInView, mounted, reducedMotion, isDark])

  useEffect(() => {
    const handleVisibility = () => {
      if (!videoRef.current || reducedMotion) return
      if (document.visibilityState === 'visible' && isInView) {
        videoRef.current.play().catch(() => {})
      } else {
        videoRef.current.pause()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [isInView, reducedMotion, isDark])

  const videoSrc = isDark ? '/media/hero-video.mp4' : '/media/hero-video-light.mp4'
  const posterSrc = isDark ? '/media/hero-poster.jpg' : '/media/hero-poster-light.jpg'

  // Elliptical feathering mask centered on active keyboard & hands
  const maskStyle: React.CSSProperties = {
    maskImage: isDark
      ? 'radial-gradient(ellipse 66% 62% at 55% 48%, black 15%, rgba(0, 0, 0, 0.8) 40%, rgba(0, 0, 0, 0.22) 65%, rgba(0, 0, 0, 0.04) 82%, transparent 95%)'
      : 'radial-gradient(ellipse 64% 60% at 55% 48%, black 12%, rgba(0, 0, 0, 0.72) 36%, rgba(0, 0, 0, 0.18) 60%, rgba(0, 0, 0, 0.03) 80%, transparent 94%)',
    WebkitMaskImage: isDark
      ? 'radial-gradient(ellipse 66% 62% at 55% 48%, black 15%, rgba(0, 0, 0, 0.8) 40%, rgba(0, 0, 0, 0.22) 65%, rgba(0, 0, 0, 0.04) 82%, transparent 95%)'
      : 'radial-gradient(ellipse 64% 60% at 55% 48%, black 12%, rgba(0, 0, 0, 0.72) 36%, rgba(0, 0, 0, 0.18) 60%, rgba(0, 0, 0, 0.03) 80%, transparent 94%)',
  }

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full overflow-hidden pointer-events-none select-none ${className}`}
      aria-hidden="true"
    >
      {/* Soft atmospheric ambient glow behind the video — naturally falls off to transparent */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: isDark
            ? 'radial-gradient(ellipse 46% 42% at 56% 48%, rgba(56, 189, 248, 0.09) 0%, rgba(99, 102, 241, 0.04) 38%, transparent 70%)'
            : 'radial-gradient(ellipse 46% 42% at 56% 48%, rgba(225, 210, 255, 0.18) 0%, rgba(255, 225, 205, 0.1) 38%, transparent 70%)',
        }}
      />

      {/* Video & Poster Container with Radial Feathering Mask */}
      <div
        className="absolute inset-0 w-full h-full flex items-center justify-center"
        style={maskStyle}
      >
        {/* High-fidelity fallback / poster image */}
        <img
          key={isDark ? 'poster-dark' : 'poster-light'}
          src={posterSrc}
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-700"
          style={{
            objectPosition: isDark ? 'center 52%' : 'center center',
            opacity: canPlay ? 0 : 0.95,
            filter: isDark ? 'brightness(1.02) contrast(1.04)' : 'brightness(1.01) contrast(1.02)',
          }}
        />

        {/* Real video layer */}
        {mounted && !reducedMotion && (
          <motion.video
            key={isDark ? 'video-dark' : 'video-light'}
            ref={videoRef}
            muted
            loop
            playsInline
            autoPlay
            preload="auto"
            onLoadedData={() => setCanPlay(true)}
            onCanPlay={() => setCanPlay(true)}
            onPlaying={() => setCanPlay(true)}
            initial={{ opacity: 0 }}
            animate={{
              opacity: canPlay ? 0.95 : 0,
            }}
            transition={{ duration: 0.6 }}
            className="absolute inset-0 w-full h-full object-cover"
            style={{
              objectPosition: isDark ? 'center 52%' : 'center center',
              filter: isDark ? 'brightness(1.02) contrast(1.04)' : 'brightness(1.01) contrast(1.02)',
            }}
          >
            <source src={videoSrc} type="video/mp4" />
          </motion.video>
        )}
      </div>

      {/* Multi-Directional Gradient Overlays guaranteeing zero seams on all 4 boundaries */}
      {/* 1. Left Edge Directional Fade — dissolves smoothly towards the headline */}
      <div
        className="absolute inset-y-0 left-0 w-[50%] pointer-events-none"
        style={{
          background:
            'linear-gradient(to right, var(--bg) 0%, rgba(var(--bg-rgb), 0.98) 22%, rgba(var(--bg-rgb), 0.5) 60%, rgba(var(--bg-rgb), 0) 100%)',
        }}
      />

      {/* 2. Bottom Edge Directional Fade — dissolves before next section begins */}
      <div
        className="absolute inset-x-0 bottom-0 h-[34%] pointer-events-none"
        style={{
          background:
            'linear-gradient(to top, var(--bg) 0%, rgba(var(--bg-rgb), 0.94) 26%, rgba(var(--bg-rgb), 0.4) 62%, rgba(var(--bg-rgb), 0) 100%)',
        }}
      />

      {/* 3. Top Edge Directional Fade — dissolves smoothly under navigation/header */}
      <div
        className="absolute inset-x-0 top-0 h-[24%] pointer-events-none"
        style={{
          background:
            'linear-gradient(to bottom, var(--bg) 0%, rgba(var(--bg-rgb), 0.88) 20%, rgba(var(--bg-rgb), 0) 100%)',
        }}
      />

      {/* 4. Right Edge Directional Fade — dissolves before viewport boundary */}
      <div
        className="absolute inset-y-0 right-0 w-[24%] pointer-events-none"
        style={{
          background:
            'linear-gradient(to left, var(--bg) 0%, rgba(var(--bg-rgb), 0.88) 20%, rgba(var(--bg-rgb), 0) 100%)',
        }}
      />
    </div>
  )
}
