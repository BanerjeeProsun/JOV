import React from 'react'
import { JLogo } from './brand/JLogo'

interface BrandLogoProps {
  compact?: boolean
  dark?: boolean
  className?: string
  animated?: boolean
  layoutId?: string
}

export const BrandLogo: React.FC<BrandLogoProps> = ({
  compact = false,
  className = '',
  animated = false,
  layoutId,
}) => {
  return (
    <JLogo
      variant={compact ? 'mark' : 'lockup'}
      size={26}
      animated={animated}
      layoutId={layoutId}
      className={className}
    />
  )
}
