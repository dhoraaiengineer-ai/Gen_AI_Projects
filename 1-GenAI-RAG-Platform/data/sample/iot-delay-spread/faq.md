# Delay spread project FAQ

## What problem does the project solve?
It predicts the RMS delay spread of indoor radio channels so that IoT links can be planned without
measuring every building.

## Which frequency bands were measured?
Measurements were taken in the 2.4 GHz and 5.8 GHz bands at five indoor sites.

## How many measurement snapshots were collected?
A total of 3,985 channel snapshots were collected across the five sites.

## Which site had the largest delay spread?
The warehouse site (S4) had the largest delay spread, 58.4 ns in NLOS conditions, because of its steel frame
and high metal shelving.

## How was the data split for training?
Sites S1, S2 and S3 were used for training and validation, and sites S4 and S5 were held out for testing.

## What software was used?
The network was built and trained in Python with PyTorch, using a custom Levenberg-Marquardt optimiser.

## Where can I read the paper?
The paper is available at https://example.org/jawe/2024/03/rms-delay-spread.pdf (DOI 10.5555/jawe.2024.0317).

Note: this is a synthetic document created to test the RAG platform. All names are fictional.
