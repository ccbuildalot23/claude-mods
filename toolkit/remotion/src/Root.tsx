import React from 'react'
import { Composition } from 'remotion'
import { Silhouette, silhouetteDefaults } from './Silhouette'

// 15-second 9:16 text video: Chris's lines over a backlit silhouette (no face, ever).
export const Root: React.FC = () => (
  <Composition
    id="Silhouette15"
    component={Silhouette}
    durationInFrames={450}
    fps={30}
    width={1080}
    height={1920}
    defaultProps={silhouetteDefaults}
  />
)
