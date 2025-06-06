import {Box, Colors, Icon, Tag, Tooltip} from '@dagster-io/ui-components';
import isEqual from 'lodash/isEqual';
import * as React from 'react';
import {Link} from 'react-router-dom';
import {UserDisplay} from 'shared/runs/UserDisplay.oss';
import styled from 'styled-components';

import {
  AssetDescription,
  AssetInsetForHoverEffect,
  AssetNameRow,
  AssetNodeBox,
  AssetNodeContainer,
} from './AssetNode';
import {AssetNodeFacet, labelForFacet} from './AssetNodeFacets';
import {assetNodeLatestEventContent, buildAssetNodeStatusContent} from './AssetNodeStatusContent';
import {LiveDataForNode, LiveDataForNodeWithStaleData} from './Utils';
import {ASSET_NODE_TAGS_HEIGHT} from './layout';
import {useAssetLiveData} from '../asset-data/AssetLiveDataProvider';
import {ChangedReasonsTag} from '../assets/ChangedReasons';
import {isAssetOverdue} from '../assets/OverdueTag';
import {StaleReasonsTag} from '../assets/Stale';
import {AssetChecksStatusSummary} from '../assets/asset-checks/AssetChecksStatusSummary';
import {assetDetailsPathForKey} from '../assets/assetDetailsPathForKey';
import {AssetKind} from '../graph/KindTags';
import {markdownToPlaintext} from '../ui/markdownToPlaintext';
import {AssetNodeFragment} from './types/AssetNode.types';

interface Props2025 {
  definition: AssetNodeFragment;
  selected: boolean;
  facets: Set<AssetNodeFacet>;
  onChangeAssetSelection?: (selection: string) => void;
}

export const ASSET_NODE_HOVER_EXPAND_HEIGHT = 3;

export const AssetNode2025 = React.memo((props: Props2025) => {
  const {liveData} = useAssetLiveData(props.definition.assetKey);
  return <AssetNodeWithLiveData {...props} liveData={liveData} />;
}, isEqual);

export const AssetNodeWithLiveData = ({
  definition,
  selected,
  facets,
  onChangeAssetSelection,
  liveData,
}: Props2025 & {liveData: LiveDataForNodeWithStaleData | undefined}) => {
  return (
    <AssetInsetForHoverEffect>
      <AssetNodeContainer $selected={selected}>
        {facets.has(AssetNodeFacet.UnsyncedTag) ? (
          <Box
            flex={{direction: 'row', justifyContent: 'space-between', alignItems: 'center'}}
            style={{minHeight: ASSET_NODE_TAGS_HEIGHT}}
          >
            <StaleReasonsTag liveData={liveData} assetKey={definition.assetKey} />
            <ChangedReasonsTag
              changedReasons={definition.changedReasons}
              assetKey={definition.assetKey}
            />
          </Box>
        ) : (
          <div style={{minHeight: ASSET_NODE_HOVER_EXPAND_HEIGHT}} />
        )}
        <AssetNodeBox $selected={selected} $isMaterializable={definition.isMaterializable}>
          <AssetNameRow definition={definition} />
          {facets.has(AssetNodeFacet.Description) && (
            <AssetNodeRow label={null}>
              {definition.description ? (
                <AssetDescription $color={Colors.textDefault()}>
                  {markdownToPlaintext(definition.description).split('\n')[0]}
                </AssetDescription>
              ) : (
                <AssetDescription $color={Colors.textDefault()}>No description</AssetDescription>
              )}
            </AssetNodeRow>
          )}
          {facets.has(AssetNodeFacet.Owner) && (
            <AssetNodeRow label={labelForFacet(AssetNodeFacet.Owner)}>
              {definition.owners.length > 0 ? (
                <SingleOwnerOrTooltip owners={definition.owners} />
              ) : null}
            </AssetNodeRow>
          )}
          {facets.has(AssetNodeFacet.LatestEvent) && (
            <AssetNodeRow label={labelForFacet(AssetNodeFacet.LatestEvent)}>
              {assetNodeLatestEventContent({definition, liveData})}
            </AssetNodeRow>
          )}
          {facets.has(AssetNodeFacet.Checks) && (
            <AssetNodeRow label={labelForFacet(AssetNodeFacet.Checks)}>
              {liveData && liveData.assetChecks.length > 0 ? (
                <Link
                  to={assetDetailsPathForKey(definition.assetKey, {view: 'checks'})}
                  onClick={(e) => e.stopPropagation()}
                >
                  <AssetChecksStatusSummary
                    liveData={liveData}
                    rendering="dag2025"
                    assetKey={definition.assetKey}
                  />
                </Link>
              ) : null}
            </AssetNodeRow>
          )}
          {facets.has(AssetNodeFacet.Freshness) && (
            <AssetNodeRow label={labelForFacet(AssetNodeFacet.Freshness)}>
              {!liveData?.freshnessInfo ? null : isAssetOverdue(liveData) ? (
                <Box flex={{gap: 4, alignItems: 'center'}}>
                  <Icon name="close" color={Colors.accentRed()} />
                  Violated
                </Box>
              ) : (
                <Box flex={{gap: 4, alignItems: 'center'}}>
                  <Icon name="done" color={Colors.accentGreen()} />
                  Passing
                </Box>
              )}
            </AssetNodeRow>
          )}
          {facets.has(AssetNodeFacet.Status) && (
            <AssetNodeStatusRow definition={definition} liveData={liveData} />
          )}
        </AssetNodeBox>
        {facets.has(AssetNodeFacet.KindTag) && (
          <Box
            style={{minHeight: ASSET_NODE_TAGS_HEIGHT}}
            flex={{alignItems: 'center', direction: 'row-reverse', gap: 8}}
          >
            {definition.kinds.map((kind) => (
              <AssetKind
                key={kind}
                kind={kind}
                style={{position: 'relative', margin: 0}}
                onChangeAssetSelection={onChangeAssetSelection}
              />
            ))}
          </Box>
        )}
      </AssetNodeContainer>
    </AssetInsetForHoverEffect>
  );
};

const AssetNodeRowBox = styled(Box)`
  white-space: nowrap;
  line-height: 12px;
  font-size: 12px;
  height: 24px;
  a:hover {
    text-decoration: none;
  }
  &:last-child {
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
  }
`;

const AssetNodeRow = ({
  label,
  children,
}: {
  label: string | null;
  children: React.ReactNode | null;
}) => {
  return (
    <AssetNodeRowBox
      padding={{horizontal: 8}}
      flex={{justifyContent: 'space-between', alignItems: 'center', gap: 6}}
      border="bottom"
    >
      {label ? <span style={{color: Colors.textLight()}}>{label}</span> : undefined}
      {children ? children : <span style={{color: Colors.textLighter()}}>–</span>}
    </AssetNodeRowBox>
  );
};

interface StatusRowProps {
  definition: AssetNodeFragment;
  liveData: LiveDataForNode | undefined;
}

const AssetNodeStatusRow = ({definition, liveData}: StatusRowProps) => {
  const {content, background} = buildAssetNodeStatusContent({
    assetKey: definition.assetKey,
    definition,
    liveData,
  });
  return (
    <AssetNodeRowBox
      background={background}
      padding={{horizontal: 8}}
      flex={{justifyContent: 'space-between', alignItems: 'center', gap: 6}}
    >
      {content}
    </AssetNodeRowBox>
  );
};

const SingleOwnerOrTooltip = ({owners}: {owners: AssetNodeFragment['owners']}) => {
  if (owners.length === 1) {
    const owner = owners[0]!;
    return owner.__typename === 'UserAssetOwner' ? (
      <UserDisplayWrapNoPadding>
        <UserDisplay email={owner.email} size="very-small" />
      </UserDisplayWrapNoPadding>
    ) : (
      <Tag icon="people">{owner.team}</Tag>
    );
  }

  return (
    <Tooltip
      placement="top"
      content={
        <Box flex={{wrap: 'wrap', gap: 12}} style={{maxWidth: 300}}>
          {owners.map((o, idx) =>
            o.__typename === 'UserAssetOwner' ? (
              <UserDisplayWrapNoPadding key={idx}>
                <UserDisplay email={o.email} size="very-small" />
              </UserDisplayWrapNoPadding>
            ) : (
              <Tag key={idx} icon="people">
                {o.team}
              </Tag>
            ),
          )}
        </Box>
      }
    >
      {`${owners.length} owners`}
    </Tooltip>
  );
};

const UserDisplayWrapNoPadding = styled.div`
  & > div > div {
    background: none;
    padding: 0;
  }
`;
